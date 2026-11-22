"""Switch platform for Novatek Electro EM."""

from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.helpers.entity import EntityCategory

from .api import EMError
from .const import STATUS_RELAY_BIT
from .coordinator import NovatekEMCoordinator
from .entity import NovatekEMEntity

_LOGGER = logging.getLogger(__name__)

RELAY_DESCRIPTION = SwitchEntityDescription(
    key="relay",
    translation_key="relay",
    icon="mdi:electric-switch",
)

SETTING_SWITCHES: dict[str, SwitchEntityDescription] = {
    "pow_enable": SwitchEntityDescription(
        key="pow_enable",
        translation_key="pow_enable",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:gauge",
    ),
    "freq_enable": SwitchEntityDescription(
        key="freq_enable",
        translation_key="freq_enable",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:pulse",
    ),
    "dst_enable": SwitchEntityDescription(
        key="dst_enable",
        translation_key="dst_enable",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:weather-sunny",
    ),
    "hctrl_enable": SwitchEntityDescription(
        key="hctrl_enable",
        translation_key="hctrl_enable",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:beach",
    ),
    "sync_sntp_enable": SwitchEntityDescription(
        key="sync_sntp_enable",
        translation_key="sync_sntp_enable",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:clock-check-outline",
    ),
    "wifi_wdt_enable": SwitchEntityDescription(
        key="wifi_wdt_enable",
        translation_key="wifi_wdt_enable",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:wifi-strength-alert-outline",
    ),
    "cloud_enable": SwitchEntityDescription(
        key="cloud_enable",
        translation_key="cloud_enable",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:cloud-upload-outline",
    ),
}


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator = entry.runtime_data.coordinator
    entities = [NovatekEMRelaySwitch(coordinator, RELAY_DESCRIPTION)]
    entities.extend(
        NovatekEMSettingSwitch(coordinator, description, param)
        for param, description in SETTING_SWITCHES.items()
    )
    async_add_entities(entities)


class NovatekEMRelaySwitch(NovatekEMEntity, SwitchEntity):
    """The load relay of the meter."""

    entity_description: SwitchEntityDescription

    def __init__(
        self,
        coordinator: NovatekEMCoordinator,
        description: SwitchEntityDescription,
    ) -> None:
        super().__init__(coordinator, f"switch_{description.key}")
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        value = self.coordinator.data.measurements.get("sys_flag")
        if value is None:
            return None
        return bool(int(value) >> STATUS_RELAY_BIT & 1)

    async def async_turn_on(self, **kwargs) -> None:
        await self._toggle(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._toggle(False)

    async def _toggle(self, on: bool) -> None:
        client = self.coordinator.entry.runtime_data.client
        _LOGGER.debug("Relay switch turned %s", "on" if on else "off")
        try:
            await client.ctrl(on)
        except EMError as err:
            _LOGGER.error("Relay control failed: %s", err)
            return
        await self.coordinator.async_request_refresh()


class NovatekEMSettingSwitch(NovatekEMEntity, SwitchEntity):
    """A boolean setting represented as a switch."""

    entity_description: SwitchEntityDescription

    def __init__(
        self,
        coordinator: NovatekEMCoordinator,
        description: SwitchEntityDescription,
        param: str,
    ) -> None:
        super().__init__(coordinator, f"switch_{description.key}")
        self.entity_description = description
        self._param = param

    @property
    def is_on(self) -> bool | None:
        value = self.coordinator.data.settings.get(self._param)
        if value is None:
            return None
        return bool(int(value))

    async def async_turn_on(self, **kwargs) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._set(False)

    async def _set(self, on: bool) -> None:
        client = self.coordinator.entry.runtime_data.client
        _LOGGER.debug("Switch %s -> %s", self._param, int(on))
        try:
            await client.set_setting(self._param, int(on))
        except EMError as err:
            _LOGGER.error("Failed to set %s: %s", self._param, err)
            return
        if self.coordinator.data:
            self.coordinator.data.settings[self._param] = int(on)
            self.coordinator.async_update_listeners()
