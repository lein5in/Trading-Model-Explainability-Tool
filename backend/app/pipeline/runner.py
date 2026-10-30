import json
import logging
import time
from app.config import Settings, get_settings
from app.pipeline.jobs import AnalysisJob
from app.pipeline.sanitize import sanitize_json
from app.pipeline.stages import (
    FATAL_STAGES,
    STAGE_FUNCTIONS,
    STAGES,
    JobState,
    JobTimeout,
    PipelineDeps,
    StageFailure,
)
from app.sandbox.runner import SandboxTimeoutError

logger = logging.getLogger(__name__)


def error_payload(code: str, message: str, stage: str | None, details: dict | None = None) -> dict:
    payload = {"code": code, "message": message, "stage": stage}
    if details:
        payload["details"] = details
    return payload


def error_text(error: dict | None) -> str | None:
    return json.dumps(sanitize_json(error)) if error else None


def run_analysis_job(job: AnalysisJob, deps: PipelineDeps, settings: Settings | None = None, clock=time.monotonic) -> None:
    settings = settings or get_settings()
    repository = deps.repository
    stages = {name: {"state": "pending", "duration_ms": None} for name in STAGES}
    state = JobState(
        job=job,
        deps=deps,
        settings=settings,
        deadline=clock() + settings.job_timeout_seconds,
        clock=clock,
        model_meta=dict(job.model_meta),
    )
    state.result["stages"] = stages
    state.result["errors"] = state.errors

    def persist(fields: dict) -> None:
        repository.update_analysis(job.analysis_id, sanitize_json(fields))

    def snapshot(**fields) -> dict:
        base = {"result": state.result, "model_meta": state.model_meta}
        if state.report is not None:
            base["report"] = state.report
        base.update(fields)
        return base

    persist(snapshot(status="running", stage=STAGES[0]))
    current = STAGES[0]
    started = clock()
    try:
        for name in STAGES:
            current = name
            state.remaining()
            stages[name]["state"] = "running"
            persist(snapshot(stage=name))
            started = clock()
            failure = None
            try:
                STAGE_FUNCTIONS[name](state)
            except (JobTimeout, SandboxTimeoutError):
                raise
            except StageFailure as exc:
                failure = exc
            except Exception as exc:
                logger.exception("Stage %s failed for analysis %s", name, job.analysis_id)
                failure = StageFailure(f"{name}_failed", f"{type(exc).__name__}: {exc}")
            stages[name]["duration_ms"] = int((clock() - started) * 1000)

            if failure is None:
                stages[name]["state"] = "done"
                persist(snapshot())
                continue

            stages[name]["state"] = "failed"
            error = error_payload(failure.code, failure.message, name, failure.details)
            state.errors.append(error)
            if name in FATAL_STAGES:
                persist(snapshot(status="failed", stage=name, error=error_text(error)))
                return
            persist(snapshot(error=error_text(state.errors[0])))

        status = "partial" if state.errors else "completed"
        persist(snapshot(status=status, stage="done", error=error_text(state.errors[0] if state.errors else None)))
    except (JobTimeout, SandboxTimeoutError):
        stages[current]["state"] = "failed"
        stages[current]["duration_ms"] = int((clock() - started) * 1000)
        error = error_payload(
            "timeout",
            f"The analysis exceeded the time limit of {settings.job_timeout_seconds:g} seconds.",
            current,
        )
        state.errors.append(error)
        persist(snapshot(status="failed", stage=current, error=error_text(error)))
    except Exception as exc:
        logger.exception("Analysis %s failed unexpectedly", job.analysis_id)
        error = error_payload("internal_error", f"{type(exc).__name__}: {exc}", current)
        state.errors.append(error)
        persist(snapshot(status="failed", stage=current, error=error_text(error)))
