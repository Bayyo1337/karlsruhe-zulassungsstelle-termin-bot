"""DataUpdateCoordinator for Karlsruhe Termin."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .konsentas import KonsentasClient

_LOGGER = logging.getLogger(__name__)


class KarlsruheTerminCoordinator(DataUpdateCoordinator[dict]):
    """Fetch appointment data and fire an HA event when an earlier slot appears."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: KonsentasClient,
        scan_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=scan_interval),
        )
        self.client = client

    async def _async_update_data(self) -> dict:
        try:
            data = await self.client.fetch_data()
        except Exception as err:
            raise UpdateFailed(f"Error fetching Konsentas data: {err}") from err

        if data.get("earlier_slot_found"):
            _LOGGER.warning(
                "Earlier appointment detected: %s < %s",
                data["earliest_available"],
                data["current_appointment"],
            )
            self.hass.bus.async_fire(
                f"{DOMAIN}_earlier_appointment",
                {
                    "current": data["current_appointment"],
                    "earlier": data["earliest_available"],
                    "manage_url": self.client.manage_url,
                },
            )

        return data
