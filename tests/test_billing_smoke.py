"""Smoke tests for BillingManager using the storage stub."""

from __future__ import annotations

import asyncio
import sys
import types
from types import SimpleNamespace

_core = sys.modules.get("homeassistant.core") or types.ModuleType(
    "homeassistant.core"
)
sys.modules.setdefault("homeassistant.core", _core)
_storage = sys.modules.get("homeassistant.helpers.storage")
if _storage is None:
    _storage = types.ModuleType("homeassistant.helpers.storage")
    sys.modules["homeassistant.helpers.storage"] = _storage

if not hasattr(_storage, "Store"):

    class Store:
        def __init__(self, hass, version, key):
            self.saved = None

        def __class_getitem__(cls, item):
            return cls

        async def async_load(self):
            return None

        async def async_save(self, data):
            self.saved = dict(data)

        def async_delay_save(self, data_func, delay):
            self.saved = dict(data_func())

    _storage.Store = Store

from novatek_em12x.billing_manager import BillingManager


class FakeCoordinator:
    def __init__(self):
        self.listeners = 0

    def async_update_listeners(self):
        self.listeners += 1


def _make():
    entry = SimpleNamespace(entry_id="e1", data={}, options={})
    events = []
    hass = SimpleNamespace(
        bus=SimpleNamespace(async_fire=lambda *a: events.append(a))
    )
    manager = BillingManager(hass, entry, FakeCoordinator())
    return manager, events


def test_first_update_initialises_baseline():
    manager, _ = _make()
    asyncio.run(manager.async_update(1500))
    assert manager.base_kwh == 1.5
    assert manager.reading == 1.5


def test_reading_follows_counter():
    manager, _ = _make()
    asyncio.run(manager.async_update(1500))
    asyncio.run(manager.async_update(2500))
    assert manager.reading == 2.5


def test_counter_reset_rebases_and_keeps_reading():
    manager, events = _make()
    asyncio.run(manager.async_update(1500))
    asyncio.run(manager.async_update(2500))
    asyncio.run(manager.async_update(100))
    assert manager.reading == 2.5
    assert manager.base_kwh == 2.5
    assert events and events[-1][1]["reason"] == "reset"


def test_manual_set_reading_fires_event():
    manager, events = _make()
    asyncio.run(manager.async_update(1500))
    asyncio.run(manager.async_set_reading(12345.678, 2000))
    assert manager.reading == 12345.678
    assert manager.device_wh_at_base == 2000
    assert events[-1][1]["reason"] == "manual"
    asyncio.run(manager.async_update(3000))
    assert manager.reading == 12345.678 + 1.0
