"""Button platform for Novatek Electro EM."""

from __future__ import annotations

import logging
import time

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.helpers.entity import EntityCategory

from .api import EMError
from .coordinator import NovatekEMCoordinator
from .entity import NovatekEMEntity

_LOGGER = logging.getLogger(__name__)

BUTTONS: tuple[ButtonEntityDescription, ...] = (
    ButtonEntityDescription(
        key="energy_reset",
        translation_key="energy_reset",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:counter",
    ),
    ButtonEntityDescription(
        key="set_time",
        translation_key="set_time",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:clock-fast",
    ),
    ButtonEntityDescription(
        key="ntp_sync",
        translation_key="ntp_sync",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:clock-check-outline",
    ),
    ButtonEntityDescription(
        key="cancel_auto_on",
        translation_key="cancel_auto_on",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:timer-remove-outline",
    ),
    ButtonEntityDescription(
        key="reboot",
        translation_key="reboot",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:restart",
    ),
)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        NovatekEMButtonEntity(coordinator, description) for description in BUTTONS
    )


class NovatekEMButtonEntity(NovatekEMEntity, ButtonEntity):
    """Button performing an action on the meter."""

    entity_description: ButtonEntityDescription

    def __init__(
        self,
        coordinator: NovatekEMCoordinator,
        description: ButtonEntityDescription,
    ) -> None:
        super().__init__(coordinator, f"button_{description.key}")
        self.entity_description = description

    async def async_press(self) -> None:
        client = self.coordinator.entry.runtime_data.client
        key = self.entity_description.key
        _LOGGER.debug("Button pressed: %s", key)
        try:
            if key == "energy_reset":
                await client.energy_reset()
            elif key == "set_time":
                await client.set_clock(int(time.time()))
            elif key == "ntp_sync":
                await client.sync_clock()
            elif key == "reboot":
                await client.reboot()
            elif key == "cancel_auto_on":
                await self.coordinator.auto_on.async_cancel()
        except EMError as err:
            _LOGGER.error("Button %s failed: %s", key, err)
        if key in ("energy_reset", "set_time"):
            await self.coordinator.async_request_refresh()
