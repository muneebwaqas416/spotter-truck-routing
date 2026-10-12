"""Departure-time handling. Pure functions; no Django or HTTP.

A driver enters departure as wall-clock time at the origin ("06:00 in Salt Lake City").
Naive datetimes are therefore interpreted in the origin's IANA timezone; offset-qualified
datetimes are trusted as given.
"""

import logging
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger(__name__)

FORECAST_HORIZON = timedelta(days=14)  # matches weather.FORECAST_DAYS
PAST_GRACE = timedelta(hours=1)  # tolerate "now" while the user is still typing


class DepartureOutOfRange(ValueError):
    """Departure is in the past or beyond the forecast horizon."""


def zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        logger.warning("Unknown timezone %r; using UTC", name)
        return ZoneInfo("UTC")


def localize(departure: datetime, tz_name: str) -> datetime:
    """Attach the origin's timezone to a naive departure; leave aware ones unchanged."""
    if departure.tzinfo is not None:
        return departure
    return departure.replace(tzinfo=zone(tz_name))


def check_departure_window(departure: datetime, now: datetime | None = None) -> None:
    """Raise if an aware departure can't be forecast: in the past or beyond the forecast."""
    now = now or datetime.now(UTC)
    if departure < now - PAST_GRACE:
        raise DepartureOutOfRange("Departure is in the past.")
    if departure > now + FORECAST_HORIZON:
        raise DepartureOutOfRange(f"Forecasts cover the next {FORECAST_HORIZON.days} days.")
