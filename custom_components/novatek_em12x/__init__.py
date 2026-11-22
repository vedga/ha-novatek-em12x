"""Support for Novatek Electro EM energy meters."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EMApiClient
from .const import DOMAIN
from .coordinator import NovatekEMCoordinator

_LOGGER = logging.getLogger(__name__)

__all__ = ["DOMAIN", "NovatekEMConfigEntry", "NovatekEMRuntimeData", "async_setup_entry", "async_unload_entry"]

type NovatekEMConfigEntry = ConfigEntry[NovatekEMRuntimeData]

PLATFORMS: list[str] = [
    "binary_sensor",
    "button",
    "datetime",
    "number",
    "select",
    "sensor",
    "switch",
    "text",
]


@dataclass
class NovatekEMRuntimeData:
    """Runtime data stored in the config entry."""

    client: EMApiClient
    coordinator: NovatekEMCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: NovatekEMConfigEntry) -> bool:
    """Set up Novatek EM from a config entry."""
    client = EMApiClient(
        entry.data[CONF_HOST],
        entry.data.get(CONF_PASSWORD, ""),
        async_get_clientsession(hass),
    )
    coordinator = NovatekEMCoordinator(hass, entry, client)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = NovatekEMRuntimeData(client, coordinator)
    entry.async_on_unload(entry.add_update_listener(options_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NovatekEMConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.client.close()
    return unload_ok


async def options_update_listener(hass: HomeAssistant, entry: NovatekEMConfigEntry) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)
