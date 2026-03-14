"""Sensor platform for Karlsruhe Termin."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import KarlsruheTerminCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: KarlsruheTerminCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            CurrentAppointmentSensor(coordinator, entry),
            EarliestAvailableSensor(coordinator, entry),
        ]
    )


class _BaseSensor(CoordinatorEntity[KarlsruheTerminCoordinator], SensorEntity):
    def __init__(
        self, coordinator: KarlsruheTerminCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="Karlsruhe Zulassungsstelle",
            manufacturer="Konsentas",
        )


class CurrentAppointmentSensor(_BaseSensor):
    """Current booked appointment — state: 'DD.MM.YYYY HH:MM'."""

    _attr_name = "Aktueller Termin"
    _attr_icon = "mdi:calendar-check"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_current_appointment"

    @property
    def native_value(self) -> str | None:
        appt = (self.coordinator.data or {}).get("current_appointment")
        if not appt:
            return None
        return f"{appt['date']} {appt['time']}"

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data or {}
        return {
            "available_days": data.get("available_appointments", []),
            "earlier_slot_found": data.get("earlier_slot_found", False),
        }


class EarliestAvailableSensor(_BaseSensor):
    """Earliest available appointment slot — state: 'DD.MM.YYYY HH:MM' or None."""

    _attr_name = "Frühester verfügbarer Termin"
    _attr_icon = "mdi:calendar-clock"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_earliest_available"

    @property
    def native_value(self) -> str | None:
        slot = (self.coordinator.data or {}).get("earliest_available")
        if not slot:
            return None
        return f"{slot['date']} {slot['time_start']}"

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data or {}
        slot = data.get("earliest_available") or {}
        return {
            "date": slot.get("date"),
            "time_start": slot.get("time_start"),
            "time_end": slot.get("time_end"),
            "places": slot.get("places"),
            "recno": slot.get("recno"),
            "is_earlier_than_current": data.get("earlier_slot_found", False),
            "all_available_days": data.get("available_appointments", []),
        }
