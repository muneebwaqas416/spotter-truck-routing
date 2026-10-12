"""Departure-time handling. Pure functions; no Django or HTTP.

A driver enters departure as wall-clock time at the origin ("06:00 in Salt Lake City").
Naive datetimes are therefore interpreted in the origin's IANA timezone; offset-qualified
datetimes are trusted as given.
"""

import logging
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger(__name__)

# Open-Meteo bills each location as one call up to 14 days and more beyond that.
FORECAST_DAYS = 14
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


def forecast_window(now: datetime) -> tuple[datetime, datetime]:
    """First and last hourly forecast instants: the forecast starts at 00:00 UTC today and covers
    FORECAST_DAYS whole days, so it ends at 23:00 UTC on the last day, not at now + 14 days."""
    start = now.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=FORECAST_DAYS) - timedelta(hours=1)


def check_departure_window(departure: datetime, now: datetime | None = None) -> None:
    """Raise if an aware departure can't be forecast: in the past or beyond the forecast."""
    now = now or datetime.now(UTC)
    first, last = forecast_window(now)
    if departure < max(now - PAST_GRACE, first):
        raise DepartureOutOfRange("Departure is in the past.")
    if departure > last:
        raise DepartureOutOfRange(
            f"Forecasts only reach {last:%b} {last.day}, {last:%H:%M} UTC. "
            "Pick an earlier departure."
        )
