"""Binary sensors for the Peak Forecast integration."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import ATTRIBUTION, DEVICE_NAME, DOMAIN, LEVEL_HIGH, MANUFACTURER
from .coordinator import PeakForecastCoordinator
from .parser import ForecastSnapshot, Slot


def _slot_at(snapshot: ForecastSnapshot, when: datetime) -> Slot | None:
    for slot in snapshot.slots:
        if slot.start <= when < slot.end:
            return slot
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PeakForecastCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            PeakActiveBinarySensor(coordinator),
            WaiverActiveBinarySensor(coordinator),
        ]
    )


class _PeakBinaryBase(CoordinatorEntity[PeakForecastCoordinator], BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

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


class PeakActiveBinarySensor(_PeakBinaryBase):
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator: PeakForecastCoordinator) -> None:
        super().__init__(coordinator, "peak_active")

    @property
    def is_on(self) -> bool | None:
        snapshot = self.coordinator.data
        if snapshot is None:
            return None
        slot = _slot_at(snapshot, dt_util.utcnow())
        return bool(slot and slot.level == LEVEL_HIGH)


class WaiverActiveBinarySensor(_PeakBinaryBase):
    def __init__(self, coordinator: PeakForecastCoordinator) -> None:
        super().__init__(coordinator, "waiver_active")

    @property
    def is_on(self) -> bool | None:
        snapshot = self.coordinator.data
        if snapshot is None:
            return None
        slot = _slot_at(snapshot, dt_util.utcnow())
        return bool(slot and slot.is_waiver)
