import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.deps import Services
from app.api.errors import register_error_handlers
from app.api.routes_analysis import router as analysis_router
from app.api.routes_meta import router as meta_router
from app.config import get_sandbox_runtime, get_settings
from app.db.repository import SupabaseRepository
from app.pipeline.jobs import JobManager
from app.pipeline.recovery import recover_interrupted
from app.pipeline.runner import run_analysis_job
from app.pipeline.sandbox_client import SandboxClient
from app.pipeline.stages import PipelineDeps
from app.reports.generator import ReportService
from app.security.rate_limit import SlidingWindowRateLimiter

logger = logging.getLogger(__name__)


def build_services(repository=None, run_job=None, sandbox=None, report_generator=None, reports=None) -> Services:
    settings = get_settings()
    repository = repository if repository is not None else SupabaseRepository()
    sandbox = sandbox if sandbox is not None else SandboxClient()
    reports = reports if reports is not None else ReportService()
    report_generator = report_generator if report_generator is not None else reports.for_state
    if run_job is None:
        deps = PipelineDeps(repository=repository, sandbox=sandbox, report_generator=report_generator)

        def run_job(job):
            run_analysis_job(job, deps)
    return Services(
        repository=repository,
        rate_limiter=SlidingWindowRateLimiter(settings.rate_limit_runs, settings.rate_limit_window_seconds),
        job_manager=JobManager(run_job, max_concurrent_jobs=settings.max_concurrent_jobs),
        sandbox=sandbox,
        report_generator=report_generator,
        reports=reports,
        report_rate_limiter=SlidingWindowRateLimiter(settings.rate_limit_runs, settings.rate_limit_window_seconds),
    )


@asynccontextmanager
async def lifespan(application: FastAPI):
    get_sandbox_runtime()
    services = application.state.services
    try:
        recovered = recover_interrupted(services.repository, get_settings().job_timeout_seconds)
        if recovered:
            logger.warning("Marked %d interrupted analyses as failed.", recovered)
    except Exception:
        logger.exception("Startup recovery of interrupted analyses failed.")
    yield
    services.job_manager.shutdown()


def create_app(services: Services | None = None) -> FastAPI:
    settings = get_settings()
    application = FastAPI(title="Trading Explainability Tool", lifespan=lifespan)
    application.state.services = services if services is not None else build_services()
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    register_error_handlers(application)
    application.include_router(meta_router)
    application.include_router(analysis_router)
    return application


app = create_app()
