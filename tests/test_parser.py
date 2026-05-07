"""Parser tests pinned to the captured 2026-05-06 fixture."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from peak_forecast.parser import ForecastParseError, parse_html

FIXTURE = Path(__file__).parent / "fixtures" / "page-2026-05-06.html"
CENTRAL = ZoneInfo("America/Chicago")


@pytest.fixture(scope="module")
def fixture_html() -> str:
    return FIXTURE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def snapshot(fixture_html):
    return parse_html(
        fixture_html,
        fetched_at=datetime(2026, 5, 6, 12, 0, tzinfo=timezone.utc),
    )


def test_total_slot_count(snapshot):
    # 7 days * 32 periods (13..44) = 224
    assert len(snapshot.slots) == 224


def test_seven_distinct_local_dates(snapshot):
    dates = {s.start.astimezone(CENTRAL).date() for s in snapshot.slots}
    assert len(dates) == 7


def test_thirty_two_periods_per_day(snapshot):
    by_date: dict[object, int] = {}
    for s in snapshot.slots:
        d = s.start.astimezone(CENTRAL).date()
        by_date[d] = by_date.get(d, 0) + 1
    assert set(by_date.values()) == {32}


def test_first_slot_is_6am_local(snapshot):
    first = min(snapshot.slots, key=lambda s: s.start)
    local = first.start.astimezone(CENTRAL)
    assert (local.hour, local.minute) == (6, 0)


def test_last_slot_starts_at_9_30pm_local(snapshot):
    last_start = max(s.start for s in snapshot.slots)
    local = last_start.astimezone(CENTRAL)
    assert (local.hour, local.minute) == (21, 30)


def test_slot_duration_is_30_minutes(snapshot):
    for s in snapshot.slots:
        assert (s.end - s.start).total_seconds() == 1800


def test_levels_only_use_known_values(snapshot):
    assert {s.level for s in snapshot.slots}.issubset({0, 1, 2})


def test_has_high_probability_slots(snapshot):
    assert any(s.level == 2 for s in snapshot.slots)


def test_has_waiver_slots(snapshot):
    waivers = [s for s in snapshot.slots if s.is_waiver]
    # Captured page had 84 waiver=true cells
    assert len(waivers) == 84


def test_fetched_at_is_utc(snapshot):
    assert snapshot.fetched_at.tzinfo is timezone.utc


def test_naive_fetched_at_is_promoted_to_utc(fixture_html):
    naive = datetime(2026, 5, 6, 12, 0)
    snap = parse_html(fixture_html, fetched_at=naive)
    assert snap.fetched_at.tzinfo is timezone.utc


def test_empty_html_raises():
    with pytest.raises(ForecastParseError):
        parse_html(
            "<html><body></body></html>",
            fetched_at=datetime(2026, 5, 6, tzinfo=timezone.utc),
        )


def test_html_without_grid_raises():
    with pytest.raises(ForecastParseError):
        parse_html(
            '<html><body><div class="something-else"></div></body></html>',
            fetched_at=datetime(2026, 5, 6, tzinfo=timezone.utc),
        )


def test_slots_are_sorted(snapshot):
    starts = [s.start for s in snapshot.slots]
    assert starts == sorted(starts)
