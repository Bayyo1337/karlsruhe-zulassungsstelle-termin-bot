"""Button platform — book the earliest available slot or cancel the appointment."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import KarlsruheTerminCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: KarlsruheTerminCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            BookEarliestButton(coordinator, entry),
            CancelAppointmentButton(coordinator, entry),
        ]
    )


class _BaseButton(ButtonEntity):
    def __init__(
        self, coordinator: KarlsruheTerminCoordinator, entry: ConfigEntry
    ) -> None:
        self._coordinator = coordinator
        self._entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="Karlsruhe Zulassungsstelle",
            manufacturer="Konsentas",
        )


class BookEarliestButton(_BaseButton):
    """Press to book the earliest available slot shown by the sensor."""

    _attr_name = "Frühesten Termin buchen"
    _attr_icon = "mdi:calendar-arrow-left"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_book_earliest"

    @property
    def available(self) -> bool:
        """Only enable the button when an earlier slot actually exists."""
        data = self._coordinator.data or {}
        return bool(data.get("earlier_slot_found") and data.get("earliest_available"))

    async def async_press(self) -> None:
        data = self._coordinator.data or {}
        slot = data.get("earliest_available")

        if not slot:
            _LOGGER.error("Cannot book: no earlier slot in coordinator data.")
            return

        _LOGGER.warning(
            "Booking earlier slot: %s %s (recno=%s)",
            slot["date"], slot["time_start"], slot["recno"],
        )

        success = await self._coordinator.client.book_slot(slot["recno"])

        if success:
            _LOGGER.warning("Booking successful! New appointment: %s %s", slot["date"], slot["time_start"])
            await self._coordinator.async_request_refresh()
        else:
            _LOGGER.error("Booking failed — verify manually at %s", data.get("manage_url"))


class CancelAppointmentButton(_BaseButton):
    """Press to cancel (stornieren) the current appointment."""

    _attr_name = "Termin stornieren"
    _attr_icon = "mdi:calendar-remove"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_cancel_appointment"

    async def async_press(self) -> None:
        data = self._coordinator.data or {}
        appt = data.get("current_appointment")

        _LOGGER.warning(
            "Cancelling appointment: %s %s — manage URL: %s",
            appt.get("date") if appt else "?",
            appt.get("time") if appt else "?",
            data.get("manage_url"),
        )

        success = await self._coordinator.client.cancel_appointment()

        if success:
            _LOGGER.warning("Cancellation request accepted by server.")
            await self._coordinator.async_request_refresh()
        else:
            _LOGGER.error(
                "Cancellation request failed — verify manually at %s",
                data.get("manage_url"),
            )
