"""Text platform for Novatek Electro EM settings."""

from __future__ import annotations

import logging

from homeassistant.components.text import TextEntity, TextMode
from homeassistant.helpers.entity import EntityCategory

from .api import EMError, decode_setting_str, encode_setting_str
from .coordinator import NovatekEMCoordinator
from .entity import NovatekEMEntity

_LOGGER = logging.getLogger(__name__)

TEXT_PARAMS = ("sync_sntp_address",)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        NovatekEMTextEntity(coordinator, param) for param in TEXT_PARAMS
    )


class NovatekEMTextEntity(NovatekEMEntity, TextEntity):
    """String setting of the meter."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min = 0
    _attr_native_max = 32
    _attr_pattern = None
    _attr_mode = TextMode.TEXT

    def __init__(self, coordinator: NovatekEMCoordinator, param: str) -> None:
        super().__init__(coordinator, f"text_{param}")
        self._param = param
        self._attr_translation_key = param

    @property
    def native_value(self) -> str:
        value = self.coordinator.data.settings.get(self._param)
        return decode_setting_str(str(value)) if value is not None else ""

    async def async_set_value(self, value: str) -> None:
        client = self.coordinator.entry.runtime_data.client
        _LOGGER.debug("Text %s -> %s", self._param, value)
        try:
            await client.set_setting(self._param, encode_setting_str(value))
        except EMError as err:
            _LOGGER.error("Failed to set %s: %s", self._param, err)
            return
        if self.coordinator.data:
            self.coordinator.data.settings[self._param] = encode_setting_str(value)
            self.coordinator.async_update_listeners()
