"""
Sliding window rate limiter backed by Redis sorted sets.

Using a custom implementation over slowapi because slowapi's Redis backend
had version conflicts with redis-py 5.x. The sliding window is more accurate
than fixed-window counters — no burst-at-boundary problem where a client sends
100 requests at :59s and 100 more at :01s of the next window.

If Redis is unavailable, rate limiting degrades gracefully (all requests pass).
"""

from __future__ import annotations

import time
from typing import Optional

import redis

from src.core.config import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)

_client: redis.Redis | None = None


def set_rate_limit_client(client: redis.Redis) -> None:
    global _client
    _client = client


class RateLimitExceeded(Exception):
    def __init__(self, limit: int, window: int):
        self.limit = limit
        self.window = window
        self.retry_after = window
        super().__init__(f"Rate limit: {limit} req/{window}s")


def check_rate_limit(identifier: str, limit: int | None = None, window: int | None = None) -> tuple[int, int]:
    """
    Returns (requests_in_window, remaining).
    Raises RateLimitExceeded if over limit.
    """
    s = get_settings()
    limit = limit or s.rate_limit_requests
    window = window or s.rate_limit_window_seconds

    if _client is None:
        return 0, limit

    key = f"rl:{identifier}"
    now = time.time()

    try:
        pipe = _client.pipeline()
        pipe.zremrangebyscore(key, 0, now - window)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, window + 1)
        results = pipe.execute()
        count = results[2]

        if count > limit:
            raise RateLimitExceeded(limit=limit, window=window)

        return count, max(0, limit - count)
    except RateLimitExceeded:
        raise
    except Exception as exc:
        logger.warning(f"Rate limit check error: {exc}")
        return 0, limit
