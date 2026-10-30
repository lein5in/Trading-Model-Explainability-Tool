import shutil
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field


@dataclass
class AnalysisJob:
    analysis_id: str
    params: dict
    model_meta: dict
    model_path: str
    work_dir: str | None = None
    csv_path: str | None = None
    extras: dict = field(default_factory=dict)


class JobManager:
    def __init__(self, run_job, max_concurrent_jobs: int = 2, max_workers: int = 8):
        self._run_job = run_job
        self._semaphore = threading.BoundedSemaphore(max_concurrent_jobs)
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="tme-job")
        self._futures: dict[str, Future] = {}
        self._lock = threading.Lock()

    def submit(self, job: AnalysisJob) -> Future:
        future = self._executor.submit(self._execute, job)
        with self._lock:
            self._futures[job.analysis_id] = future
        return future

    def _execute(self, job: AnalysisJob) -> None:
        try:
            with self._semaphore:
                self._run_job(job)
        finally:
            if job.work_dir:
                shutil.rmtree(job.work_dir, ignore_errors=True)

    def wait(self, analysis_id: str, timeout: float | None = None) -> None:
        with self._lock:
            future = self._futures.get(analysis_id)
        if future is not None:
            future.exception(timeout=timeout)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
