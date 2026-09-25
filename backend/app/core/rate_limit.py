import time
from collections import defaultdict, deque

from app.core.exceptions import RateLimitError


class RateLimiter:
    """Sliding-window limiter. State lives in this process's memory, so with several
    workers each one counts separately; move to Redis when you scale out."""

    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque] = defaultdict(deque)

    def _trim(self, key: str) -> deque:
        q, now = self._hits[key], time.monotonic()
        while q and now - q[0] > self.window:
            q.popleft()
        if not q:
            self._hits.pop(key, None)
        return q

    def check(self, key: str) -> None:
        """Raise 429 if the key is already at its limit (does not count as a hit)."""
        q = self._trim(key)
        if len(q) >= self.limit:
            raise RateLimitError(int(self.window - (time.monotonic() - q[0])) + 1)

    def hit(self, key: str) -> None:
        self._trim(key)
        self._hits[key].append(time.monotonic())

    def reset(self, key: str) -> None:
        self._hits.pop(key, None)
