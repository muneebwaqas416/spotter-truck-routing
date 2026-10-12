from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from routing.services.timezones import DepartureOutOfRange, check_departure_window, localize

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


@pytest.mark.parametrize(
    ("offset", "ok"),
    [
        (timedelta(hours=-1), True),  # within the grace period
        (timedelta(hours=-1, seconds=-1), False),
        (timedelta(days=14), True),
        (timedelta(days=14, seconds=1), False),
    ],
)
def test_departure_window_boundaries(offset, ok):
    if ok:
        check_departure_window(NOW + offset, now=NOW)
    else:
        with pytest.raises(DepartureOutOfRange):
            check_departure_window(NOW + offset, now=NOW)
