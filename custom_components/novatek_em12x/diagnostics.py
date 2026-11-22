"""Diagnostics support for Novatek Electro EM."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.const import CONF_HOST, CONF_PASSWORD

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from . import NovatekEMConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: NovatekEMConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime = entry.runtime_data
    data = runtime.coordinator.data
    entry_data = {
        key: value for key, value in entry.data.items() if key != CONF_PASSWORD
    }
    entry_data["password_set"] = bool(entry.data.get(CONF_PASSWORD))
    return {
        "entry": {
            "title": entry.title,
            "unique_id": entry.unique_id,
            "host": entry.data.get(CONF_HOST),
            "data": entry_data,
            "options": dict(entry.options),
        },
        "last_update_success": runtime.coordinator.last_update_success,
        "measurements": dict(data.measurements) if data else {},
        "settings": dict(data.settings) if data else {},
        "cloud": dict(data.cloud) if data else {},
    }
