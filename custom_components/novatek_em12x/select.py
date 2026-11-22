"""Select platform for Novatek Electro EM settings."""

from __future__ import annotations

import logging
from typing import ClassVar

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.entity import EntityCategory

from .api import EMError
from .const import COST_UNITS, COUNT_APV_OPTIONS
from .coordinator import NovatekEMCoordinator
from .entity import NovatekEMEntity

_LOGGER = logging.getLogger(__name__)

COUNT_APV_PARAMS = (
    "volt_count_apv",
    "cur_count_apv",
    "pow_count_apv",
    "freq_count_apv",
)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator = entry.runtime_data.coordinator
    entities: list[SelectEntity] = [
        NovatekEMCountApvSelect(coordinator, param) for param in COUNT_APV_PARAMS
    ]
    entities.append(NovatekEMCurrencySelect(coordinator))
    async_add_entities(entities)


class NovatekEMCountAppSelectBase(NovatekEMEntity, SelectEntity):
    """Base for select entities."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: NovatekEMCoordinator, key: str) -> None:
        super().__init__(coordinator, f"select_{key}")
        self._param = key
        self._attr_translation_key = key


class NovatekEMCountApvSelect(NovatekEMCountAppSelectBase):
    """Reclose count setting: forbidden / N attempts / always."""

    _attr_options: ClassVar[list[str]] = [str(option) for option in COUNT_APV_OPTIONS]

    @property
    def current_option(self) -> str | None:
        value = self.coordinator.data.settings.get(self._param)
        if value is None:
            return None
        try:
            option = str(int(value))
        except (TypeError, ValueError):
            _LOGGER.warning("Unexpected value for %s: %r", self._param, value)
            return None
        if option not in self.options:
            _LOGGER.warning(
                "Value %s of %s is not a known option", option, self._param
            )
            return None
        return option

    async def async_select_option(self, option: str) -> None:
        await self._set(int(option))

    async def _set(self, value: int) -> None:
        client = self.coordinator.entry.runtime_data.client
        _LOGGER.debug("Select %s -> %s", self._param, value)
        try:
            await client.set_setting(self._param, value)
        except EMError as err:
            _LOGGER.error("Failed to set %s: %s", self._param, err)
            await self.coordinator.async_request_refresh()
            return
        if self.coordinator.data:
            self.coordinator.data.settings[self._param] = value
            self.coordinator.async_update_listeners()


class NovatekEMCurrencySelect(NovatekEMCountAppSelectBase):
    """Energy tariff currency."""

    _attr_options: ClassVar[list[str]] = list(COST_UNITS)

    def __init__(self, coordinator: NovatekEMCoordinator) -> None:
        super().__init__(coordinator, "cost_unit")

    @property
    def current_option(self) -> str | None:
        value = self.coordinator.data.settings.get("cost_unit")
        if value is None:
            return None
        try:
            index = int(value)
        except (TypeError, ValueError):
            return None
        if 0 <= index < len(COST_UNITS):
            return COST_UNITS[index]
        return None

    async def async_select_option(self, option: str) -> None:
        index = COST_UNITS.index(option)
        client = self.coordinator.entry.runtime_data.client
        _LOGGER.debug("Select cost_unit -> %s (%s)", option, index)
        try:
            await client.set_setting("cost_unit", index)
        except EMError as err:
            _LOGGER.error("Failed to set cost_unit: %s", err)
            await self.coordinator.async_request_refresh()
            return
        if self.coordinator.data:
            self.coordinator.data.settings["cost_unit"] = index
            self.coordinator.async_update_listeners()
