"""Karlsruhe Zulassungsstelle appointment monitor."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_MIN_NOTICE_DAYS,
    CONF_SCAN_INTERVAL,
    CONF_TIME_WINDOW_END,
    CONF_TIME_WINDOW_START,
    CONF_VORGANGSNR,
    CONF_ZUGANGSCODE,
    DEFAULT_MIN_NOTICE_DAYS,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIME_WINDOW_END,
    DEFAULT_TIME_WINDOW_START,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import KarlsruheTerminCoordinator
from .konsentas import KonsentasClient


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    client = KonsentasClient(
        vorgangsnr=entry.data[CONF_VORGANGSNR],
        zugangscode=entry.data[CONF_ZUGANGSCODE],
        time_window_start=entry.data.get(CONF_TIME_WINDOW_START, DEFAULT_TIME_WINDOW_START),
        time_window_end=entry.data.get(CONF_TIME_WINDOW_END, DEFAULT_TIME_WINDOW_END),
        min_notice_days=entry.data.get(CONF_MIN_NOTICE_DAYS, DEFAULT_MIN_NOTICE_DAYS),
    )
    coordinator = KarlsruheTerminCoordinator(
        hass,
        client=client,
        scan_interval=entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded
