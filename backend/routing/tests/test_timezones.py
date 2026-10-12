from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from routing.services.timezones import (
    DepartureOutOfRange,
    check_departure_window,
    forecast_window,
    localize,
)

NOW = datetime(2026, 10, 10, 21, 0, tzinfo=UTC)


def test_naive_departure_gets_origin_zone_with_dst_offset():
    summer = localize(datetime(2026, 7, 1, 6, 0), "America/Denver")
    winter = localize(datetime(2026, 12, 1, 6, 0), "America/Denver")
    assert summer.utcoffset() == timedelta(hours=-6)  # MDT
    assert winter.utcoffset() == timedelta(hours=-7)  # MST
    assert summer.astimezone(UTC).hour == 12


def test_aware_departure_is_kept_as_given():
    # The reported trip: 06:00 GMT+5 is 01:00 UTC, i.e. 19:00 MDT the previous evening.
    aware = datetime(2026, 10, 11, 6, 0, tzinfo=ZoneInfo("Asia/Karachi"))
    assert localize(aware, "America/Denver") is aware
    assert aware.astimezone(ZoneInfo("America/Denver")) == datetime(
        2026, 10, 10, 19, 0, tzinfo=ZoneInfo("America/Denver")
    )


def test_unknown_zone_falls_back_to_utc():
    assert localize(datetime(2026, 10, 11, 6, 0), "Not/AZone").utcoffset() == timedelta(0)


# NOW is Oct 10 21:00 UTC, so the forecast runs Oct 10 00:00 → Oct 23 23:00 UTC.
LAST_FORECAST_HOUR = datetime(2026, 10, 23, 23, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("departure", "ok"),
    [
        (NOW - timedelta(hours=1), True),  # within the grace period
        (NOW - timedelta(hours=1, seconds=1), False),
        (LAST_FORECAST_HOUR, True),
        (LAST_FORECAST_HOUR + timedelta(seconds=1), False),
        # Regression: now + 14 days was accepted, but the forecast ends 22 h earlier.
        (NOW + timedelta(days=14), False),
    ],
)
def test_departure_window_matches_forecast_coverage(departure, ok):
    if ok:
        check_departure_window(departure, now=NOW)
    else:
        with pytest.raises(DepartureOutOfRange):
            check_departure_window(departure, now=NOW)


def test_grace_period_never_reaches_before_the_forecast_starts():
    """Just after midnight UTC, "1 hour ago" is yesterday, which today's forecast doesn't cover."""
    just_after_midnight = datetime(2026, 10, 11, 0, 20, tzinfo=UTC)
    check_departure_window(just_after_midnight - timedelta(minutes=20), now=just_after_midnight)
    with pytest.raises(DepartureOutOfRange, match="in the past"):
        check_departure_window(just_after_midnight - timedelta(minutes=30), now=just_after_midnight)


def test_forecast_window_is_whole_utc_days():
    assert forecast_window(NOW) == (datetime(2026, 10, 10, tzinfo=UTC), LAST_FORECAST_HOUR)
