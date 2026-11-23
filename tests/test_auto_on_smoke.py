"""Smoke tests for AutoOnManager using minimal Home Assistant stubs."""

from __future__ import annotations

import asyncio
import sys
import types
from types import SimpleNamespace


def _module(name: str) -> types.ModuleType:
    mod = sys.modules.get(name)
    if mod is None:
        mod = types.ModuleType(name)
        sys.modules[name] = mod
    return mod


ha = _module("homeassistant")
if not hasattr(ha, "__path__"):
    ha.__path__ = []
helpers = _module("homeassistant.helpers")
if not hasattr(helpers, "__path__"):
    helpers.__path__ = []
_core = _module("homeassistant.core")
_event = _module("homeassistant.helpers.event")
_storage = _module("homeassistant.helpers.storage")

SCHEDULED: list[float] = []


def _async_call_later(hass, delay, callback):
    SCHEDULED.append(delay)
    return lambda: None


class Store:
    def __init__(self, hass, version, key):
        self.hass = hass
        self.version = version
        self.key = key
        self.saved: dict | None = None

    def __class_getitem__(cls, item):
        return cls

    async def async_load(self):
        return None

    async def async_save(self, data):
        self.saved = dict(data)

    def async_delay_save(self, data_func, delay):
        self.saved = dict(data_func())


_event.async_call_later = _async_call_later
_storage.Store = Store

from novatek_em12x.auto_on import AutoOnManager


class FakeClient:
    def __init__(self, ctrl_ok: bool = True):
        self.ctrl_ok = ctrl_ok
        self.ctrl_calls: list[bool] = []
        self.events: list[list] = []
        self.run_called = False

    async def get(self, param):
        return 0

    async def schedule(self):
        return list(self.events)

    async def schedule_add(self, when, repeat, live):
        self.events.append([when, repeat, live, 0, 1])

    async def schedule_run(self):
        self.run_called = True

    async def schedule_clear(self):
        self.events.clear()

    async def ctrl(self, on):
        self.ctrl_calls.append(on)
        if not self.ctrl_ok:
            from novatek_em12x.api import EMConnectionError

            raise EMConnectionError("offline")


class FakeCoordinator:
    def __init__(self):
        self.listeners = 0
        self.refreshes = 0

    def async_update_listeners(self):
        self.listeners += 1

    async def async_request_refresh(self):
        self.refreshes += 1


def _make_manager(options, ctrl_ok=True):
    entry = SimpleNamespace(entry_id="e1", options=options, data={})
    bus_events: list[tuple] = []
    hass = SimpleNamespace(
        bus=SimpleNamespace(async_fire=lambda *a: bus_events.append(a))
    )
    client = FakeClient(ctrl_ok)
    coordinator = FakeCoordinator()
    manager = AutoOnManager(hass, entry, client, coordinator)
    return manager, client, coordinator, bus_events


OPTIONS = {
    "auto_on_enabled": True,
    "auto_on_delay": 10,
    "auto_on_days": 1,
    "auto_on_external": True,
    "auto_on_retry": 5,
    "auto_on_horizon": 1,
}


def test_manual_arm_creates_device_event():
    SCHEDULED.clear()
    manager, client, _, _ = _make_manager(dict(OPTIONS))
    asyncio.run(manager.async_arm("manual"))
    assert manager.deadline is not None
    assert len(client.events) == 1
    assert client.events[0][1] == 0
    assert client.events[0][2] == 86400
    assert client.run_called
    assert SCHEDULED


def test_manual_attempt_failure_keeps_armed():
    manager, _client, _coordinator, bus_events = _make_manager(
        dict(OPTIONS), ctrl_ok=False
    )
    asyncio.run(manager.async_arm("manual"))
    import time

    asyncio.run(manager.async_attempt())
    assert manager.deadline is not None
    assert manager.deadline > int(time.time())
    assert manager.reason == "manual"
    assert not bus_events


def test_manual_attempt_success_finishes():
    manager, client, _coordinator, bus_events = _make_manager(dict(OPTIONS))
    asyncio.run(manager.async_arm("manual"))
    asyncio.run(manager.async_attempt())
    assert client.ctrl_calls == [True]
    assert manager.deadline is None
    assert client.events == []
    assert bus_events and bus_events[0][1]["reason"] == "auto-on"


def test_expected_state_consumed_once():
    manager, _, _, _ = _make_manager(dict(OPTIONS))
    manager.note_command(False)
    assert manager.consume_expected(False) is True
    assert manager.consume_expected(False) is False
    manager.note_command(True)
    assert manager.consume_expected(False) is False


def test_external_arm_chain_days():
    manager, client, _, _ = _make_manager(dict(OPTIONS, auto_on_days=3))
    asyncio.run(manager.async_arm("external"))
    assert len(client.events) == 3
    steps = [b[0] - a[0] for a, b in zip(client.events, client.events[1:])]
    assert steps == [86340, 86340]


def test_pause_cancels_and_blocks_arming():
    manager, client, _, _ = _make_manager(dict(OPTIONS))
    asyncio.run(manager.async_arm("manual"))
    asyncio.run(manager.async_set_paused(True))
    assert manager.paused is True
    assert manager.deadline is None
    assert client.events == []
    asyncio.run(manager.async_arm("manual"))
    assert manager.deadline is None
