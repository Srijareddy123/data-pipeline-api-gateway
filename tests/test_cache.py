from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import src.core.cache as cache_mod


@pytest.fixture(autouse=True)
def reset_cache():
    """Isolate the module-level _client between tests."""
    original = cache_mod._client
    yield
    cache_mod._client = original


# ---------------------------------------------------------------------------
# When client is None (Redis unavailable)
# ---------------------------------------------------------------------------

def test_cache_get_returns_none_when_unavailable():
    cache_mod._client = None
    assert cache_mod.cache_get("prefix", {"k": "v"}) is None


def test_cache_set_is_noop_when_unavailable():
    cache_mod._client = None
    cache_mod.cache_set("prefix", {"k": "v"}, {"data": 1})  # should not raise


def test_cache_invalidate_returns_zero_when_unavailable():
    cache_mod._client = None
    assert cache_mod.cache_invalidate("prefix") == 0


def test_cache_stats_unavailable():
    cache_mod._client = None
    stats = cache_mod.cache_stats()
    assert stats["status"] == "unavailable"


# ---------------------------------------------------------------------------
# Normal operation with a mock Redis client
# ---------------------------------------------------------------------------

def test_cache_get_hit():
    mock = MagicMock()
    mock.get.return_value = '{"result": 42}'
    cache_mod._client = mock

    result = cache_mod.cache_get("test", {"page": 1})
    assert result == {"result": 42}
    mock.get.assert_called_once()


def test_cache_get_miss():
    mock = MagicMock()
    mock.get.return_value = None
    cache_mod._client = mock

    result = cache_mod.cache_get("test", {"page": 1})
    assert result is None


def test_cache_set_calls_setex():
    mock = MagicMock()
    cache_mod._client = mock

    with patch("src.core.cache.get_settings") as mock_settings:
        mock_settings.return_value.cache_ttl_seconds = 300
        cache_mod.cache_set("test", {"page": 1}, {"data": "hello"})

    mock.setex.assert_called_once()
    args = mock.setex.call_args[0]
    assert args[0].startswith("gateway:test:")
    assert args[1] == 300


def test_cache_set_uses_custom_ttl():
    mock = MagicMock()
    cache_mod._client = mock

    with patch("src.core.cache.get_settings") as mock_settings:
        mock_settings.return_value.cache_ttl_seconds = 300
        cache_mod.cache_set("test", {}, {"x": 1}, ttl=3600)

    args = mock.setex.call_args[0]
    assert args[1] == 3600


def test_cache_get_handles_redis_error_gracefully():
    mock = MagicMock()
    mock.get.side_effect = Exception("connection timeout")
    cache_mod._client = mock

    result = cache_mod.cache_get("test", {})
    assert result is None  # degrades gracefully, no exception raised


def test_cache_set_handles_redis_error_gracefully():
    mock = MagicMock()
    mock.setex.side_effect = Exception("connection timeout")
    cache_mod._client = mock

    with patch("src.core.cache.get_settings") as mock_settings:
        mock_settings.return_value.cache_ttl_seconds = 300
        cache_mod.cache_set("test", {}, {"data": 1})  # should not raise


def test_cache_key_is_deterministic():
    key1 = cache_mod._key("vehicles", {"page": 1, "make": "Honda"})
    key2 = cache_mod._key("vehicles", {"make": "Honda", "page": 1})
    assert key1 == key2  # sort_keys=True makes order irrelevant


def test_cache_invalidate_deletes_matching_keys():
    mock = MagicMock()
    mock.scan_iter.return_value = ["gateway:vehicles:abc", "gateway:vehicles:def"]
    mock.delete.return_value = 2
    cache_mod._client = mock

    count = cache_mod.cache_invalidate("vehicles")
    assert count == 2
    mock.delete.assert_called_once()


def test_cache_stats_ok():
    mock = MagicMock()
    mock.info.return_value = {
        "used_memory_human": "1.5M",
        "connected_clients": 3,
        "keyspace_hits": 100,
        "keyspace_misses": 5,
    }
    cache_mod._client = mock

    stats = cache_mod.cache_stats()
    assert stats["status"] == "ok"
    assert stats["keyspace_hits"] == 100
