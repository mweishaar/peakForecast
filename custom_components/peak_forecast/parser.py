"""Parse the Capital Electric peak-forecast HTML grid into a structured snapshot."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from .const import (
    LEVEL_HIGH,
    LEVEL_LOW,
    LEVEL_MEDIUM,
    LEVEL_UNKNOWN,
    PERIOD_DURATION_MINUTES,
    SOURCE_TIMEZONE,
)


@dataclass(frozen=True, slots=True)
class Slot:
    start: datetime
    end: datetime
    level: int
    original_level: int
    is_waiver: bool


@dataclass(frozen=True, slots=True)
class ForecastSnapshot:
    fetched_at: datetime
    slots: tuple[Slot, ...]


class ForecastParseError(ValueError):
    """Raised when the page does not contain the expected forecast grid."""


_CLASS_TO_LEVEL = {
    "peak-low": LEVEL_LOW,
    "peak-medium": LEVEL_MEDIUM,
    "peak-high": LEVEL_HIGH,
    "peak-unknown": LEVEL_UNKNOWN,
}


def _to_int(value: object, default: int) -> int:
    if value is None:
        return default
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def _level_from_classes(classes: list[str]) -> int:
    for cls in classes:
        if cls in _CLASS_TO_LEVEL:
            return _CLASS_TO_LEVEL[cls]
    return LEVEL_UNKNOWN


def _slot_bounds(d: _date, period: int, tz: ZoneInfo) -> tuple[datetime, datetime]:
    start_local = datetime(d.year, d.month, d.day, tzinfo=tz) + timedelta(
        minutes=(period - 1) * PERIOD_DURATION_MINUTES
    )
    end_local = start_local + timedelta(minutes=PERIOD_DURATION_MINUTES)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def parse_html(
    html: str,
    *,
    fetched_at: datetime,
    source_tz: ZoneInfo | None = None,
) -> ForecastSnapshot:
    """Parse forecast HTML; raise ForecastParseError if the grid is missing/empty."""
    tz = source_tz or ZoneInfo(SOURCE_TIMEZONE)
    soup = BeautifulSoup(html, "html.parser")
    cells = soup.select("div.forecast-cell[data-date][data-period]")
    if not cells:
        raise ForecastParseError("no forecast cells found in page")

    slots: list[Slot] = []
    for cell in cells:
        date_str = cell.get("data-date")
        period_str = cell.get("data-period")
        if not date_str or not period_str:
            continue
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d").date()
            period = int(period_str)
        except ValueError:
            continue

        classes = cell.get("class") or []
        level_from_class = _level_from_classes(list(classes))
        level = _to_int(cell.get("data-value"), level_from_class)
        original = _to_int(cell.get("data-original-value"), level)
        is_waiver = (cell.get("data-is-waiver") or "false").strip().lower() == "true"

        start, end = _slot_bounds(d, period, tz)
        slots.append(
            Slot(
                start=start,
                end=end,
                level=level,
                original_level=original,
                is_waiver=is_waiver,
            )
        )

    if not slots:
        raise ForecastParseError("forecast cells were present but none parsed")

    slots.sort(key=lambda s: (s.start, s.end))
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)
    else:
        fetched_at = fetched_at.astimezone(timezone.utc)
    return ForecastSnapshot(fetched_at=fetched_at, slots=tuple(slots))
