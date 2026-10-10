from unittest.mock import Mock, patch

import pytest
from django.core.cache import cache
from redis.exceptions import ConnectionError as RedisConnectionError

from routing.cache import get_many_or_fetch, get_or_fetch


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()


def test_fetches_once_then_serves_from_cache() -> None:
    fetch = Mock(return_value={"wind_mph": 38})

    assert get_or_fetch("wx:1", 60, fetch) == {"wind_mph": 38}
    assert get_or_fetch("wx:1", 60, fetch) == {"wind_mph": 38}
    fetch.assert_called_once()


def test_failed_fetch_is_not_cached() -> None:
    failing = Mock(side_effect=TimeoutError("provider down"))
    with pytest.raises(TimeoutError):
        get_or_fetch("wx:2", 60, failing)

    recovered = Mock(return_value={"wind_mph": 10})
    assert get_or_fetch("wx:2", 60, recovered) == {"wind_mph": 10}
    recovered.assert_called_once()


def test_falsy_values_are_cached() -> None:
    fetch = Mock(return_value=[])
    get_or_fetch("geo:none", 60, fetch)
    get_or_fetch("geo:none", 60, fetch)
    fetch.assert_called_once()


def test_cache_outage_falls_back_to_direct_fetch() -> None:
    fetch = Mock(return_value="fresh")
    with (
        patch("routing.cache.cache.get", side_effect=RedisConnectionError("down")),
        patch("routing.cache.cache.set_many") as cache_set,
    ):
        assert get_or_fetch("wx:3", 60, fetch) == "fresh"
    fetch.assert_called_once()
    cache_set.assert_not_called()


def test_get_many_fetches_only_missing_keys_in_one_batch() -> None:
    cache.set("wx:a", "cached-a")
    fetch_missing = Mock(side_effect=lambda keys: {k: f"fresh-{k}" for k in keys})

    result = get_many_or_fetch(["wx:a", "wx:b", "wx:c", "wx:b"], 60, fetch_missing)

    assert result == {"wx:a": "cached-a", "wx:b": "fresh-wx:b", "wx:c": "fresh-wx:c"}
    fetch_missing.assert_called_once_with(["wx:b", "wx:c"])
    assert cache.get("wx:c") == "fresh-wx:c"
