import json
import os
import shutil
import tempfile
from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from pydantic import BaseModel
from app.api.deps import Services, get_services
from app.api.errors import ApiError
from app.api.submission import enforce_daily_cap, enforce_rate_limit, validate_submission
from app.config import get_settings
from app.demo_models.registry import demo_model_path
from app.pipeline.jobs import AnalysisJob
from app.pipeline.sanitize import sanitize_json
from app.pipeline.runner import error_payload, error_text
from app.pipeline.stages import STAGES
from app.reports.generator import ReportError
from app.reports.slices import SECTION_IDS, build_slices
from app.security.client_ip import get_client_ip, hash_client_ip

router = APIRouter(prefix="/analysis", tags=["analysis"])

REPORTABLE_STATUSES = ("completed", "partial")


class ExplainSectionRequest(BaseModel):
    section_id: str


PUBLIC_ANALYSIS_FIELDS = ("id", "created_at", "status", "stage", "params", "model_meta", "result", "report")


def parse_error(raw):
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return {"code": "unknown_error", "message": str(raw)}


def load_analysis_or_404(services: Services, analysis_id: str) -> dict:
    row = services.repository.get_analysis(analysis_id)
    if row is None:
        raise ApiError(404, "analysis_not_found", "Analysis not found.")
    return row


def public_analysis(row: dict) -> dict:
    body = {field: row.get(field) for field in PUBLIC_ANALYSIS_FIELDS}
    body["error"] = parse_error(row.get("error"))
    return sanitize_json(body)


@router.post("/run", status_code=202)
def run_analysis(
    request: Request,
    model_file: UploadFile | None = File(None),
    demo_model_id: str | None = Form(None),
    ticker: str | None = Form(None),
    start_date: str | None = Form(None),
    end_date: str | None = Form(None),
    feature_ids: str | None = Form(None),
    csv_file: UploadFile | None = File(None),
    fee_bps: float = Form(5.0),
    slippage_bps: float = Form(2.0),
    services: Services = Depends(get_services),
):
    settings = get_settings()
    ip_hash = hash_client_ip(get_client_ip(request, settings.trust_proxy), settings.ip_hash_salt)
    enforce_rate_limit(services.rate_limiter, ip_hash)
    enforce_daily_cap(services.repository, settings.daily_analysis_cap)

    submission = validate_submission(
        settings, model_file, demo_model_id, ticker, start_date, end_date,
        feature_ids, csv_file, fee_bps, slippage_bps,
    )

    work_dir = tempfile.mkdtemp(prefix="tme_job_")
    try:
        if submission.model_source == "upload":
            extension = os.path.splitext(submission.model_filename)[1].lower()
            model_path = os.path.join(work_dir, f"model{extension}")
            with open(model_path, "wb") as f:
                f.write(submission.model_bytes)
            model_meta = {
                "filename": submission.model_filename,
                "size": len(submission.model_bytes),
                "source": "upload",
            }
        else:
            model_path = demo_model_path(submission.demo_entry)
            model_meta = {
                "filename": submission.demo_entry["file"],
                "size": os.path.getsize(model_path) if os.path.exists(model_path) else None,
                "source": "demo",
                "demo_model_id": submission.demo_entry["id"],
                "name": submission.demo_entry.get("name"),
            }
        model_meta["feature_columns"] = submission.params["feature_ids"]

        csv_path = None
        if submission.csv_bytes is not None:
            csv_path = os.path.join(work_dir, "data.csv")
            with open(csv_path, "wb") as f:
                f.write(submission.csv_bytes)

        row = services.repository.create_analysis({
            "status": "queued",
            "stage": "validate",
            "params": submission.params,
            "model_meta": model_meta,
            "client_ip_hash": ip_hash,
        })
        job = AnalysisJob(
            analysis_id=str(row["id"]),
            params=submission.params,
            model_meta=model_meta,
            model_path=model_path,
            work_dir=work_dir,
            csv_path=csv_path,
        )
    except BaseException:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise

    services.job_manager.submit(job)
    return {"analysis_id": job.analysis_id}


@router.get("/{analysis_id}/status")
def get_analysis_status(analysis_id: str, services: Services = Depends(get_services)):
    row = load_analysis_or_404(services, analysis_id)
    result = row.get("result") or {}
    return sanitize_json({
        "analysis_id": row["id"],
        "status": row.get("status"),
        "stage": row.get("stage"),
        "stages": result.get("stages") or {name: {"state": "pending", "duration_ms": None} for name in STAGES},
        "error": parse_error(row.get("error")),
    })


@router.get("/{analysis_id}")
def get_analysis(analysis_id: str, services: Services = Depends(get_services)):
    return public_analysis(load_analysis_or_404(services, analysis_id))


def client_key(request: Request) -> str:
    settings = get_settings()
    return hash_client_ip(get_client_ip(request, settings.trust_proxy), settings.ip_hash_salt)


def load_reportable(services: Services, analysis_id: str) -> dict:
    row = load_analysis_or_404(services, analysis_id)
    if not (row.get("result") or {}).get("backtest"):
        raise ApiError(409, "analysis_not_ready", "The analysis has no computed backtest to report on yet.")
    return row


@router.post("/{analysis_id}/report")
def regenerate_report(analysis_id: str, request: Request, services: Services = Depends(get_services)):
    enforce_rate_limit(services.report_rate_limiter, client_key(request))
    row = load_reportable(services, analysis_id)
    report = services.reports.for_row(row)
    result = row["result"]
    errors = [error for error in result.get("errors") or [] if error.get("stage") != "report"]
    stages = result.get("stages") or {}
    if report["status"] == "ok":
        stages.setdefault("report", {})["state"] = "done"
    else:
        stages.setdefault("report", {})["state"] = "failed"
        errors.append(error_payload(report["error"]["code"], report["error"]["message"], "report"))
    result["errors"] = errors
    result["stages"] = stages
    fields = {"report": report, "result": result}
    if row.get("status") in REPORTABLE_STATUSES:
        fields["status"] = "partial" if errors else "completed"
        fields["error"] = error_text(errors[0]) if errors else None
    services.repository.update_analysis(analysis_id, sanitize_json(fields))
    return sanitize_json(report)


@router.post("/{analysis_id}/explain-section")
def explain_section(analysis_id: str, body: ExplainSectionRequest, request: Request, services: Services = Depends(get_services)):
    enforce_rate_limit(services.report_rate_limiter, client_key(request))
    if body.section_id not in SECTION_IDS:
        raise ApiError(400, "invalid_section", f"section_id must be one of {list(SECTION_IDS)}.")
    row = load_reportable(services, analysis_id)
    slices = build_slices(row["result"], row.get("params") or {}, row.get("model_meta") or {})
    try:
        explanation = services.reports.explain_section(slices, body.section_id)
    except ReportError as exc:
        status = 503 if exc.code == "report_api_key_missing" else 502
        raise ApiError(status, exc.code, exc.message)
    return sanitize_json(explanation)
