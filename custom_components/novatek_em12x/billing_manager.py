"""Persisted external meter baseline and reading."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.storage import Store

from .billing import compute_reading, should_rebase
from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from . import NovatekEMConfigEntry

_LOGGER = logging.getLogger(__name__)

EVENT_BILLING = f"{DOMAIN}_billing"


class BillingManager:
    """Map the device energy counter to an external billing meter reading."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: NovatekEMConfigEntry,
        coordinator: Any,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.coordinator = coordinator
        self._store: Store[dict[str, Any]] = Store(
            hass, 1, f"{DOMAIN}.{entry.entry_id}.billing"
        )
        self._loaded = False
        self.base_kwh: float | None = None
        self.device_wh_at_base: int | None = None
        self.last_device_wh: int | None = None
        self.reading: float | None = None
        self.updated_at: int | None = None

    async def async_load(self) -> None:
        data = await self._store.async_load() or {}
        self.base_kwh = data.get("base_kwh")
        self.device_wh_at_base = data.get("device_wh_at_base")
        self.last_device_wh = data.get("last_device_wh")
        self.reading = data.get("reading")
        self.updated_at = data.get("updated_at")
        self._loaded = True

    def _data(self) -> dict[str, Any]:
        return {
            "base_kwh": self.base_kwh,
            "device_wh_at_base": self.device_wh_at_base,
            "last_device_wh": self.last_device_wh,
            "reading": self.reading,
            "updated_at": self.updated_at,
        }

    async def _save(self, delay: float = 0) -> None:
        data = self._data()
        if delay:
            self._store.async_delay_save(lambda: data, delay)
        else:
            await self._store.async_save(data)

    def _fire(self, reason: str, value: float | None) -> None:
        self.hass.bus.async_fire(
            EVENT_BILLING,
            {
                "entry_id": self.entry.entry_id,
                "reason": reason,
                "value": value,
                "base_kwh": self.base_kwh,
                "device_wh_at_base": self.device_wh_at_base,
            },
        )

    async def async_update(self, device_wh: int) -> None:
        """Update the reading; rebase automatically if the counter was reset."""
        if not self._loaded:
            await self.async_load()
        device_wh = int(device_wh)
        if self.base_kwh is None or self.device_wh_at_base is None:
            self.base_kwh = round(device_wh / 1000, 3)
            self.device_wh_at_base = device_wh
            self.last_device_wh = device_wh
            self.reading = self.base_kwh
            self.updated_at = int(time.time())
            await self._save()
            return
        if should_rebase(self.last_device_wh, device_wh):
            previous = self.reading if self.reading is not None else self.base_kwh
            _LOGGER.info(
                "Device energy counter reset (%s -> %s Wh), rebasing external meter",
                self.last_device_wh,
                device_wh,
            )
            self.base_kwh = round(float(previous), 3)
            self.device_wh_at_base = device_wh
            self.updated_at = int(time.time())
            self._fire("reset", self.base_kwh)
        self.last_device_wh = device_wh
        self.reading = compute_reading(
            self.base_kwh, self.device_wh_at_base, device_wh
        )
        await self._save(delay=60)

    async def async_set_reading(self, value: float, device_wh: int) -> None:
        """Rebase the external reading to the current device counter."""
        if not self._loaded:
            await self.async_load()
        device_wh = int(device_wh)
        self.base_kwh = round(float(value), 3)
        self.device_wh_at_base = device_wh
        self.last_device_wh = device_wh
        self.reading = self.base_kwh
        self.updated_at = int(time.time())
        await self._save()
        self._fire("manual", self.base_kwh)
        self.coordinator.async_update_listeners()
        _LOGGER.info("External meter rebased to %s kWh", self.base_kwh)
