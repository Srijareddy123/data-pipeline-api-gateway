from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import src.core.rate_limit as rl_mod
from src.core.rate_limit import RateLimitExceeded, check_rate_limit


@pytest.fixture(autouse=True)
def reset_rl_client():
    original = rl_mod._client
    yield
    rl_mod._client = original


# ---------------------------------------------------------------------------
# Graceful degradation when Redis is unavailable
# ---------------------------------------------------------------------------

def test_passes_when_no_redis():
    rl_mod._client = None
    count, remaining = check_rate_limit("ip:127.0.0.1", limit=10, window=60)
    assert count == 0
    assert remaining == 10


# ---------------------------------------------------------------------------
# Normal operation
# ---------------------------------------------------------------------------

def test_counts_within_limit():
    mock = MagicMock()
    mock.pipeline.return_value.__enter__ = lambda s: s
    mock.pipeline.return_value.__exit__ = MagicMock(return_value=False)

    pipe = MagicMock()
    pipe.execute.return_value = [None, None, 5, None]  # [zremrange, zadd, zcard=5, expire]
    mock.pipeline.return_value = pipe

    rl_mod._client = mock

    with patch("src.core.rate_limit.get_settings") as mock_settings:
        mock_settings.return_value.rate_limit_requests = 100
        mock_settings.return_value.rate_limit_window_seconds = 60
        count, remaining = check_rate_limit("ip:1.2.3.4", limit=100, window=60)

    assert count == 5
    assert remaining == 95


def test_raises_when_over_limit():
    mock = MagicMock()
    pipe = MagicMock()
    pipe.execute.return_value = [None, None, 101, None]  # zcard=101, over limit=100
    mock.pipeline.return_value = pipe

    rl_mod._client = mock

    with pytest.raises(RateLimitExceeded) as exc_info:
        with patch("src.core.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value.rate_limit_requests = 100
            mock_settings.return_value.rate_limit_window_seconds = 60
            check_rate_limit("ip:1.2.3.4", limit=100, window=60)

    assert exc_info.value.limit == 100
    assert exc_info.value.retry_after == 60


def test_rate_limit_exceeded_attributes():
    exc = RateLimitExceeded(limit=50, window=30)
    assert exc.limit == 50
    assert exc.window == 30
    assert exc.retry_after == 30


def test_degrades_on_redis_error():
    mock = MagicMock()
    pipe = MagicMock()
    pipe.execute.side_effect = Exception("Redis timeout")
    mock.pipeline.return_value = pipe

    rl_mod._client = mock

    with patch("src.core.rate_limit.get_settings") as mock_settings:
        mock_settings.return_value.rate_limit_requests = 100
        mock_settings.return_value.rate_limit_window_seconds = 60
        count, remaining = check_rate_limit("ip:1.2.3.4", limit=100, window=60)

    assert count == 0
    assert remaining == 100


def test_uses_settings_defaults_when_no_explicit_limits():
    mock = MagicMock()
    pipe = MagicMock()
    pipe.execute.return_value = [None, None, 1, None]
    mock.pipeline.return_value = pipe

    rl_mod._client = mock

    with patch("src.core.rate_limit.get_settings") as mock_settings:
        mock_settings.return_value.rate_limit_requests = 200
        mock_settings.return_value.rate_limit_window_seconds = 120
        count, remaining = check_rate_limit("ip:1.2.3.4")

    assert remaining == 199
