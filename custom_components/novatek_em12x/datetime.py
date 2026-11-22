"""DateTime platform for Novatek Electro EM vacation mode."""

from __future__ import annotations

import logging
from datetime import datetime

from homeassistant.components.datetime import DateTimeEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.util import dt as dt_util

from .api import EMError
from .coordinator import NovatekEMCoordinator
from .entity import NovatekEMEntity

_LOGGER = logging.getLogger(__name__)

DATETIME_PARAMS = ("hctrl_from", "hctrl_to")


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        NovatekEMDateTimeEntity(coordinator, param) for param in DATETIME_PARAMS
    )


class NovatekEMDateTimeEntity(NovatekEMEntity, DateTimeEntity):
    """Vacation start/end timestamps."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator: NovatekEMCoordinator, param: str
    ) -> None:
        super().__init__(coordinator, f"datetime_{param}")
        self._param = param
        self._attr_translation_key = param

    @property
    def native_value(self) -> datetime | None:
        value = self.coordinator.data.settings.get(self._param)
        if value is None:
            return None
        try:
            return dt_util.as_local(
                datetime.fromtimestamp(int(value), tz=dt_util.UTC)
            )
        except (TypeError, ValueError, OSError):
            return None

    async def async_set_value(self, value: datetime) -> None:
        client = self.coordinator.entry.runtime_data.client
        timestamp = int(value.timestamp())
        _LOGGER.debug("Datetime %s -> %s", self._param, timestamp)
        try:
            await client.set_setting(self._param, timestamp)
        except EMError as err:
            _LOGGER.error("Failed to set %s: %s", self._param, err)
            return
        if self.coordinator.data:
            self.coordinator.data.settings[self._param] = timestamp
            self.coordinator.async_update_listeners()
