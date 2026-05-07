"""Sensor entities for the Peak Forecast integration."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    ATTRIBUTION,
    DEVICE_NAME,
    DOMAIN,
    LEVEL_HIGH,
    LEVEL_NAMES,
    LEVEL_UNKNOWN,
    MANUFACTURER,
    PERIOD_DURATION_MINUTES,
)
from .coordinator import PeakForecastCoordinator
from .parser import ForecastSnapshot, Slot

LEVEL_OPTIONS = ["low", "medium", "high", "unknown"]


def _slot_at(snapshot: ForecastSnapshot, when: datetime) -> Slot | None:
    for slot in snapshot.slots:
        if slot.start <= when < slot.end:
            return slot
    return None


def _slots_on_local_date(snapshot: ForecastSnapshot, now_local: datetime) -> list[Slot]:
    today = now_local.date()
    tz = now_local.tzinfo
    return [s for s in snapshot.slots if s.start.astimezone(tz).date() == today]


def _next_high_block(
    snapshot: ForecastSnapshot, when: datetime
) -> tuple[datetime, datetime] | None:
    upcoming = [s for s in snapshot.slots if s.level == LEVEL_HIGH and s.end > when]
    if not upcoming:
        return None
    upcoming.sort(key=lambda s: s.start)
    start = upcoming[0].start
    end = upcoming[0].end
    for slot in upcoming[1:]:
        if slot.start == end:
            end = slot.end
        else:
            break
    return start, end


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PeakForecastCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            CurrentLevelSensor(coordinator),
            TodayMaxSensor(coordinator),
            NextHighStartSensor(coordinator),
            NextHighEndSensor(coordinator),
            HighHoursTodaySensor(coordinator),
            ForecastGridSensor(coordinator),
        ]
    )


class _PeakSensorBase(CoordinatorEntity[PeakForecastCoordinator], SensorEntity):
    """Common boilerplate: device grouping, attribution, optional minute ticks."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION
    _uses_clock = False

    def __init__(self, coordinator: PeakForecastCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry_id)},
            name=DEVICE_NAME,
            manufacturer=MANUFACTURER,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://capitalelec.com/peak-forecast",
        )
        self._unsub_minute: Callable[[], None] | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self._uses_clock:
            self._unsub_minute = async_track_time_change(
                self.hass, self._minute_tick, second=0
            )

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_minute is not None:
            self._unsub_minute()
            self._unsub_minute = None
        await super().async_will_remove_from_hass()

    @callback
    def _minute_tick(self, _now: datetime) -> None:
        if self.hass is not None:
            self.async_write_ha_state()


class CurrentLevelSensor(_PeakSensorBase):
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = LEVEL_OPTIONS
    _uses_clock = True

    def __init__(self, coordinator: PeakForecastCoordinator) -> None:
        super().__init__(coordinator, "current_level")

    @property
    def native_value(self) -> str | None:
        snapshot = self.coordinator.data
        if snapshot is None:
            return None
        slot = _slot_at(snapshot, dt_util.utcnow())
        if slot is None:
            return LEVEL_NAMES[LEVEL_UNKNOWN]
        return LEVEL_NAMES.get(slot.level, LEVEL_NAMES[LEVEL_UNKNOWN])

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        snapshot = self.coordinator.data
        if snapshot is None:
            return None
        slot = _slot_at(snapshot, dt_util.utcnow())
        if slot is None:
            return None
        return {
            "slot_start": slot.start.isoformat(),
            "slot_end": slot.end.isoformat(),
            "is_waiver": slot.is_waiver,
            "original_level": LEVEL_NAMES.get(slot.original_level, "unknown"),
        }


class TodayMaxSensor(_PeakSensorBase):
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = LEVEL_OPTIONS
    _uses_clock = True

    def __init__(self, coordinator: PeakForecastCoordinator) -> None:
        super().__init__(coordinator, "today_max")

    @property
    def native_value(self) -> str | None:
        snapshot = self.coordinator.data
        if snapshot is None:
            return None
        now_local = dt_util.now()
        today_slots = _slots_on_local_date(snapshot, now_local)
        if not today_slots:
            return LEVEL_NAMES[LEVEL_UNKNOWN]
        max_level = max(s.level for s in today_slots)
        return LEVEL_NAMES.get(max_level, LEVEL_NAMES[LEVEL_UNKNOWN])


class NextHighStartSensor(_PeakSensorBase):
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _uses_clock = True

    def __init__(self, coordinator: PeakForecastCoordinator) -> None:
        super().__init__(coordinator, "next_high_start")

    @property
    def native_value(self) -> datetime | None:
        snapshot = self.coordinator.data
        if snapshot is None:
            return None
        block = _next_high_block(snapshot, dt_util.utcnow())
        return block[0] if block else None


class NextHighEndSensor(_PeakSensorBase):
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _uses_clock = True

    def __init__(self, coordinator: PeakForecastCoordinator) -> None:
        super().__init__(coordinator, "next_high_end")

    @property
    def native_value(self) -> datetime | None:
        snapshot = self.coordinator.data
        if snapshot is None:
            return None
        block = _next_high_block(snapshot, dt_util.utcnow())
        return block[1] if block else None


class HighHoursTodaySensor(_PeakSensorBase):
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1
    _uses_clock = True

    def __init__(self, coordinator: PeakForecastCoordinator) -> None:
        super().__init__(coordinator, "high_hours_today")

    @property
    def native_value(self) -> float | None:
        snapshot = self.coordinator.data
        if snapshot is None:
            return None
        now_local = dt_util.now()
        today_slots = _slots_on_local_date(snapshot, now_local)
        high_count = sum(1 for s in today_slots if s.level == LEVEL_HIGH)
        return round(high_count * (PERIOD_DURATION_MINUTES / 60.0), 2)


class ForecastGridSensor(_PeakSensorBase):
    """Carries the full 7-day grid in attributes for the Lovelace card."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: PeakForecastCoordinator) -> None:
        super().__init__(coordinator, "grid")

    @property
    def native_value(self) -> datetime | None:
        snapshot = self.coordinator.data
        return snapshot.fetched_at if snapshot else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        snapshot = self.coordinator.data
        if snapshot is None:
            return None
        return {
            "fetched_at": snapshot.fetched_at.isoformat(),
            "slot_count": len(snapshot.slots),
            "slots": [
                {
                    "start": s.start.isoformat(),
                    "level": s.level,
                    "waiver": s.is_waiver,
                }
                for s in snapshot.slots
            ],
        }
