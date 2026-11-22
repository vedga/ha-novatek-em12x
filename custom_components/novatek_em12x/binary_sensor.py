"""Binary sensor platform for Novatek Electro EM."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.helpers.entity import EntityCategory

from .const import FAULT_BITS, STATUS_PANEL_LOCKED_BIT
from .coordinator import NovatekEMCoordinator
from .entity import NovatekEMEntity

PROBLEM_ICONS = {
    0: "mdi:flash-alert",
    1: "mdi:flash-off",
    2: "mdi:flash-alert",
    3: "mdi:reload",
    4: "mdi:current-ac",
    5: "mdi:current-ac",
    6: "mdi:reload",
    7: "mdi:gauge",
    8: "mdi:reload",
    9: "mdi:thermometer-alert",
    10: "mdi:thermometer-off",
    11: "mdi:thermometer-alert",
    12: "mdi:clock-alert",
    13: "mdi:electric-switch",
    14: "mdi:timer-off",
    15: "mdi:pulse",
    16: "mdi:pulse",
    17: "mdi:reload",
    30: "mdi:tune",
    31: "mdi:cog-off",
}

FAULT_SENSORS: dict[int, BinarySensorEntityDescription] = {
    bit: BinarySensorEntityDescription(
        key=f"fault_{key}",
        translation_key=f"fault_{key}",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon=PROBLEM_ICONS.get(bit),
    )
    for bit, key in FAULT_BITS.items()
}

STATUS_SENSORS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="panel_locked",
        translation_key="panel_locked",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:lock",
    ),
)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator = entry.runtime_data.coordinator
    entities = [
        NovatekEMFaultEntity(coordinator, description, bit)
        for bit, description in FAULT_SENSORS.items()
    ]
    entities.append(NovatekEMPanelLockEntity(coordinator, STATUS_SENSORS[0]))
    async_add_entities(entities)


class NovatekEMFaultEntity(NovatekEMEntity, BinarySensorEntity):
    """Fault flag binary sensor."""

    entity_description: BinarySensorEntityDescription

    def __init__(
        self,
        coordinator: NovatekEMCoordinator,
        description: BinarySensorEntityDescription,
        bit: int,
    ) -> None:
        super().__init__(coordinator, f"binary_sensor_{description.key}")
        self.entity_description = description
        self._bit = bit

    @property
    def is_on(self) -> bool | None:
        value = self.coordinator.data.measurements.get("faul_flag")
        if value is None:
            return None
        return bool(int(value) >> self._bit & 1)


class NovatekEMPanelLockEntity(NovatekEMEntity, BinarySensorEntity):
    """Panel lock status binary sensor."""

    entity_description: BinarySensorEntityDescription

    def __init__(
        self,
        coordinator: NovatekEMCoordinator,
        description: BinarySensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, f"binary_sensor_{description.key}")
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        value = self.coordinator.data.measurements.get("sys_flag")
        if value is None:
            return None
        return bool(int(value) >> STATUS_PANEL_LOCKED_BIT & 1)
