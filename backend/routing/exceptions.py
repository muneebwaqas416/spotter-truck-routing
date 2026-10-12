"""Typed errors for upstream providers and their mapping to HTTP responses."""

import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

from routing.services.timezones import DepartureOutOfRange

logger = logging.getLogger(__name__)


class ProviderError(Exception):
    """An upstream provider (routing, geocoding, weather) failed or returned unusable data."""

    status_code = status.HTTP_502_BAD_GATEWAY
    default_code = "provider_error"

    def __init__(self, provider: str, detail: str) -> None:
        super().__init__(f"{provider}: {detail}")
        self.provider = provider
        self.detail = detail


class ProviderTimeout(ProviderError):
    """An upstream provider did not respond within the configured timeout."""

    status_code = status.HTTP_504_GATEWAY_TIMEOUT
    default_code = "provider_timeout"


class ProviderBusy(ProviderError):
    """An upstream provider rate-limited us (HTTP 429). Temporary, so the client may retry."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_code = "provider_busy"

    def __init__(self, provider: str, retry_after_s: int) -> None:
        super().__init__(provider, "rate limited")
        self.retry_after_s = retry_after_s


class PlaceNotFound(Exception):
    """Geocoding returned no match. `field` is the request field it came from, when known."""

    def __init__(self, query: str, field: str | None = None) -> None:
        super().__init__(query)
        self.query = query
        self.field = field


class NoRouteFound(Exception):
    """The routing provider found no truck route between the two places."""


def api_exception_handler(exc: Exception, context: dict) -> Response | None:
    """Extend DRF's handler so domain and provider failures map to clear, safe responses."""
    if isinstance(exc, DepartureOutOfRange):
        return Response({"departure_time": [str(exc)]}, status=status.HTTP_400_BAD_REQUEST)
    if isinstance(exc, PlaceNotFound):
        message = f'Couldn\'t find "{exc.query}". Pick a place from the suggestions.'
        body = {"code": "place_not_found", "detail": message}
        if exc.field:
            body[exc.field] = [message]
        return Response(body, status=status.HTTP_400_BAD_REQUEST)
    if isinstance(exc, NoRouteFound):
        return Response(
            {"code": "no_route", "detail": "No truck route was found between these places."},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    if isinstance(exc, ProviderBusy):
        logger.warning("Provider rate limit (%s); retry after %ss", exc.provider, exc.retry_after_s)
        return Response(
            {
                "code": exc.default_code,
                "detail": f"The {exc.provider} service is busy. Try again in a minute.",
            },
            status=exc.status_code,
            headers={"Retry-After": str(exc.retry_after_s)},
        )
    if isinstance(exc, ProviderError):
        logger.warning("Provider failure (%s): %s", exc.provider, exc.detail)
        return Response(
            {"code": exc.default_code, "detail": f"The {exc.provider} service is unavailable."},
            status=exc.status_code,
        )
    return exception_handler(exc, context)
