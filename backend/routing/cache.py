"""Read-through cache for provider data that degrades to a direct fetch when the cache is down.

Only successful fetches are stored: if a fetch raises, nothing is cached, so a transient provider
failure never becomes a cached "unknown". Keys are versioned (v1:...) by the callers; bump the
version when a cached payload's shape changes.
"""

import logging
from collections.abc import Callable, Iterable

from django.core.cache import cache
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

_MISSING = object()


def get_or_fetch[T](key: str, ttl_seconds: int, fetch: Callable[[], T]) -> T:
    """Cached value for `key`, or the result of `fetch()` (then cached)."""
    try:
        cached = cache.get(key, _MISSING)
    except RedisError:
        logger.warning("Cache read failed for %s; fetching directly", key, exc_info=True)
        return fetch()
    if cached is not _MISSING:
        return cached  # type: ignore[return-value]

    value = fetch()
    _safe_set_many({key: value}, ttl_seconds)
    return value


def get_many_or_fetch[T](
    keys: Iterable[str],
    ttl_seconds: int,
    fetch_missing: Callable[[list[str]], dict[str, T]],
) -> dict[str, T]:
    """Cached values for `keys`; the misses are fetched in one call so providers can batch."""
    keys = list(dict.fromkeys(keys))
    try:
        found: dict[str, T] = cache.get_many(keys)
    except RedisError:
        logger.warning("Cache read failed for %d keys; fetching directly", len(keys), exc_info=True)
        found = {}

    missing = [key for key in keys if key not in found]
    if missing:
        fetched = fetch_missing(missing)
        _safe_set_many(fetched, ttl_seconds)
        found.update(fetched)
    return found


def _safe_set_many(values: dict, ttl_seconds: int) -> None:
    try:
        cache.set_many(values, ttl_seconds)
    except RedisError:
        logger.warning("Cache write failed for %d keys", len(values), exc_info=True)
