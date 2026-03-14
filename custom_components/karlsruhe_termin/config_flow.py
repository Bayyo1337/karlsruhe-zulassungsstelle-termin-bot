"""Config flow for Karlsruhe Termin integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_SCAN_INTERVAL,
    CONF_VORGANGSNR,
    CONF_ZUGANGSCODE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .konsentas import KonsentasClient

STEP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_VORGANGSNR): str,
        vol.Required(CONF_ZUGANGSCODE): str,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
            int, vol.Range(min=1, max=60)
        ),
    }
)


class KarlsruheTerminConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the setup UI."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            vorgangsnr = user_input[CONF_VORGANGSNR].strip()
            zugangscode = user_input[CONF_ZUGANGSCODE].strip()

            client = KonsentasClient(vorgangsnr, zugangscode)
            valid = await client.validate()

            if valid:
                await self.async_set_unique_id(vorgangsnr)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Termin {vorgangsnr}",
                    data={
                        CONF_VORGANGSNR: vorgangsnr,
                        CONF_ZUGANGSCODE: zugangscode,
                        CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                    },
                )
            else:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_SCHEMA,
            errors=errors,
        )
