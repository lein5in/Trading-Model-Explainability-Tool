import json
from datetime import datetime, timedelta, timezone

INTERRUPTED_STATUSES = ["queued", "running"]


def recover_interrupted(repository, timeout_seconds: float, now: datetime | None = None) -> int:
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(seconds=timeout_seconds)
    stale = repository.list_analyses_with_status(INTERRUPTED_STATUSES, cutoff)
    for row in stale:
        repository.update_analysis(row["id"], {
            "status": "failed",
            "error": json.dumps({
                "code": "interrupted",
                "message": "The analysis was interrupted by a server restart.",
                "stage": row.get("stage"),
            }),
        })
    return len(stale)
