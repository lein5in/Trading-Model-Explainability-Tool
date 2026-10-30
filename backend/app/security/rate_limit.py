import threading
import time
from collections import deque


class SlidingWindowRateLimiter:
    def __init__(self, max_events: int, window_seconds: float, clock=time.monotonic):
        self.max_events = max_events
        self.window_seconds = window_seconds
        self._clock = clock
        self._events: dict[str, deque] = {}
        self._lock = threading.Lock()

    def hit(self, key: str) -> bool:
        now = self._clock()
        with self._lock:
            events = self._events.setdefault(key, deque())
            while events and events[0] <= now - self.window_seconds:
                events.popleft()
            if len(events) >= self.max_events:
                return False
            events.append(now)
            return True

    def retry_after_seconds(self, key: str) -> int:
        now = self._clock()
        with self._lock:
            events = self._events.get(key)
            if not events:
                return 0
            return max(int(events[0] + self.window_seconds - now) + 1, 0)
