from dataclasses import dataclass
from fastapi import Request
from app.pipeline.jobs import JobManager
from app.security.rate_limit import SlidingWindowRateLimiter


@dataclass
class Services:
    repository: object
    rate_limiter: SlidingWindowRateLimiter
    job_manager: JobManager
    sandbox: object
    report_generator: object
    reports: object
    report_rate_limiter: SlidingWindowRateLimiter


def get_services(request: Request) -> Services:
    return request.app.state.services
