"""Rate limiting that stays available when the shared cache is not."""

import logging

from redis.exceptions import RedisError
from rest_framework.throttling import ScopedRateThrottle

logger = logging.getLogger(__name__)


class FailOpenScopedRateThrottle(ScopedRateThrottle):
    """ScopedRateThrottle that allows the request if Redis is unreachable.

    Throttle counters live in the cache; refusing all traffic because Redis blipped would turn a
    cache outage into a full outage.
    """

    def allow_request(self, request, view) -> bool:
        try:
            return super().allow_request(request, view)
        except RedisError:
            logger.warning("Throttle cache unavailable; allowing request", exc_info=True)
            return True
