"""One place for outbound HTTP: explicit timeouts and provider errors that never leak URLs.

Provider URLs carry API keys in the query string, so exception messages and logs here never
include the request URL.
"""

import logging
from typing import Any

import httpx
from django.conf import settings

from routing.exceptions import ProviderError, ProviderTimeout

logger = logging.getLogger(__name__)


def get_json(provider: str, url: str, params: dict[str, Any]) -> Any:
    timeout = httpx.Timeout(settings.HTTP_READ_TIMEOUT_S, connect=settings.HTTP_CONNECT_TIMEOUT_S)
    try:
        response = httpx.get(url, params=params, timeout=timeout)
    except httpx.TimeoutException as exc:
        raise ProviderTimeout(provider, "request timed out") from exc
    except httpx.HTTPError as exc:
        raise ProviderError(provider, f"request failed ({type(exc).__name__})") from exc

    if response.status_code >= 400:
        logger.warning(
            "%s returned HTTP %s: %s", provider, response.status_code, response.text[:300]
        )
        raise ProviderError(provider, f"HTTP {response.status_code}")
    try:
        return response.json()
    except ValueError as exc:
        raise ProviderError(provider, "response was not valid JSON") from exc
