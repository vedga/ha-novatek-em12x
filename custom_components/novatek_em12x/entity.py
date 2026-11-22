"""Base entity for Novatek Electro EM."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL_NAMES
from .coordinator import NovatekEMCoordinator


class NovatekEMEntity(CoordinatorEntity[NovatekEMCoordinator]):
    """Common base class for all Novatek EM entities."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: NovatekEMCoordinator, key: str
    ) -> None:
        super().__init__(coordinator)
        entry = coordinator.entry
        mac = str(entry.data.get("mac", entry.unique_id or "unknown"))
        self._attr_unique_id = f"{mac}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            name=str(entry.data.get("name") or "Novatek EM"),
            manufacturer=MANUFACTURER,
            model=MODEL_NAMES.get(entry.data.get("device_id"), "EM"),
            sw_version=entry.data.get("sw_version"),
        )
