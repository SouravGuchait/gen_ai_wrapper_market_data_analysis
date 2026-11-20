class RateLimiter:
    """Fixed-window counter kept in memory for this process."""

    def __init__(self, limit: int, window_seconds: float) -> None:
        self._limit: int = limit
        self._window_seconds: float = window_seconds
        self._events: dict[str, list[float]] = {}

    def allow(self, key: str, now: float) -> bool:
        window_start = now - self._window_seconds
        recent = [stamp for stamp in self._events.get(key, []) if stamp > window_start]
        if len(recent) >= self._limit:
            self._events[key] = recent
            return False
        recent.append(now)
        self._events[key] = recent
        return True
