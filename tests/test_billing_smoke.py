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

import novatek_em12x.billing_manager as billing_manager_module
from novatek_em12x.billing_manager import BillingManager


class FakeCoordinator:
    def __init__(self):
        self.listeners = 0

    def async_update_listeners(self):
        self.listeners += 1


def _make(options=None):
    entry = SimpleNamespace(entry_id="e1", data={}, options=options or {})
    events = []
    hass = SimpleNamespace(
        bus=SimpleNamespace(async_fire=lambda *a: events.append(a))
    )
    manager = BillingManager(hass, entry, FakeCoordinator())
    return manager, events


class _FakeClock:
    def __init__(self):
        self.now = 1000000

    def time(self):
        return self.now


def _fake_time(monkeypatch):
    clock = _FakeClock()
    monkeypatch.setattr(
        billing_manager_module, "time", SimpleNamespace(time=clock.time)
    )
    return clock


# The true model behind the fake commercial meter below:
# 1 W self-consumption and a 2 % overcount of the device counter.
# Each correction advances the fake clock by 2 hours.
_CORRECTIONS = [
    (7200, 2000, 2.022),
    (7200, 5000, 5.084),
    (7200, 6000, 6.106),
]


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


def test_auto_tune_updates_coefficients(monkeypatch):
    clock = _fake_time(monkeypatch)
    manager, events = _make()
    asyncio.run(manager.async_update(1000))
    for dt, wh, kwh in _CORRECTIONS:
        clock.now += dt
        asyncio.run(manager.async_set_reading(kwh, wh))
    assert abs(manager.self_power_w - 1.0) < 0.05
    assert abs(manager.calibration_pct - 2.0) < 0.1
    last = events[-1][1]
    assert last["reason"] == "manual"
    assert last["auto_tuned"] is True
    assert last["history_points"] == 4


def test_auto_tune_disabled_keeps_coefficients(monkeypatch):
    clock = _fake_time(monkeypatch)
    manager, events = _make(options={"billing_auto_tune": False})
    asyncio.run(manager.async_update(1000))
    for dt, wh, kwh in _CORRECTIONS:
        clock.now += dt
        asyncio.run(manager.async_set_reading(kwh, wh))
    assert manager.self_power_w == 0.0
    assert manager.calibration_pct == 0.0
    last = events[-1][1]
    assert last["auto_tuned"] is False
    assert last["suggested_self_power_w"] is not None
    assert last["suggested_calibration_pct"] is not None


def test_auto_tune_needs_three_corrections(monkeypatch):
    clock = _fake_time(monkeypatch)
    manager, _ = _make()
    asyncio.run(manager.async_update(1000))
    for dt, wh, kwh in _CORRECTIONS[:2]:
        clock.now += dt
        asyncio.run(manager.async_set_reading(kwh, wh))
    assert manager.self_power_w == 0.0
    assert manager.calibration_pct == 0.0


def test_self_power_applies_between_corrections(monkeypatch):
    clock = _fake_time(monkeypatch)
    manager, _ = _make()
    asyncio.run(manager.async_update(1000))
    asyncio.run(manager.async_set_self_power(1.0))
    clock.now += 36000
    asyncio.run(manager.async_update(1000))
    # 1 W over 10 hours = 0.01 kWh
    assert manager.reading == 1.01


def test_calibration_scales_counter(monkeypatch):
    _fake_time(monkeypatch)
    manager, _ = _make()
    asyncio.run(manager.async_update(1000))
    asyncio.run(manager.async_set_calibration(5.0))
    asyncio.run(manager.async_update(2000))
    # 1 kWh counter delta scaled by +5 % (the maximum)
    assert manager.reading == 2.05


def test_manual_coefficients_reset_history(monkeypatch):
    clock = _fake_time(monkeypatch)
    manager, events = _make()
    asyncio.run(manager.async_update(1000))
    for dt, wh, kwh in _CORRECTIONS:
        clock.now += dt
        asyncio.run(manager.async_set_reading(kwh, wh))
    assert len(manager.history) == 4
    asyncio.run(manager.async_set_self_power(1.5))
    assert manager.self_power_w == 1.5
    assert len(manager.history) == 1
    event = events[-1][1]
    assert event["reason"] == "coefficients"
    assert event["field"] == "self_power_w"
    asyncio.run(manager.async_set_calibration(-2.0))
    assert manager.calibration_pct == -2.0
    assert len(manager.history) == 1
    assert events[-1][1]["field"] == "calibration_pct"


def test_coefficients_are_clamped(monkeypatch):
    _fake_time(monkeypatch)
    manager, _ = _make()
    asyncio.run(manager.async_update(1000))
    asyncio.run(manager.async_set_self_power(99.0))
    assert manager.self_power_w == 20.0
    asyncio.run(manager.async_set_self_power(-3.0))
    assert manager.self_power_w == 0.0
    asyncio.run(manager.async_set_calibration(99.0))
    assert manager.calibration_pct == 5.0
    asyncio.run(manager.async_set_calibration(-99.0))
    assert manager.calibration_pct == -5.0
