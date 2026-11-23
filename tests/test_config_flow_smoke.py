"""Smoke tests for the config/options flows using minimal HA stubs."""

from __future__ import annotations

import asyncio
import sys
import types
from types import SimpleNamespace

import voluptuous as vol


def _install_ha_stubs() -> None:
    def module(name: str) -> types.ModuleType:
        mod = sys.modules.get(name)
        if mod is None:
            mod = types.ModuleType(name)
            sys.modules[name] = mod
        return mod

    ha = module("homeassistant")
    ha.__path__ = []
    ce = module("homeassistant.config_entries")
    const = module("homeassistant.const")
    core = module("homeassistant.core")
    helpers = module("homeassistant.helpers")
    helpers.__path__ = []
    aio = module("homeassistant.helpers.aiohttp_client")
    selector = module("homeassistant.helpers.selector")

    class ConfigFlow:
        def __init_subclass__(cls, **kwargs):
            super().__init_subclass__()

        def __init__(self):
            self.hass = None
            self.context = {}

        def async_show_form(self, **kwargs):
            return {"type": "form", **kwargs}

        def async_create_entry(self, **kwargs):
            return {"type": "create_entry", **kwargs}

        async def async_set_unique_id(self, *args, **kwargs):
            return None

        def _abort_if_unique_id_configured(self):
            return None

        def _abort_if_unique_id_mismatch(self, **kwargs):
            return None

        def _get_reconfigure_entry(self):
            return SimpleNamespace(title="EM-129", data={})

        def _get_reauth_entry(self):
            return SimpleNamespace(title="EM-129", data={})

        def async_update_reload_and_abort(self, *args, **kwargs):
            return {"type": "abort"}

    class OptionsFlow:
        def async_show_form(self, **kwargs):
            return {"type": "form", **kwargs}

        def async_create_entry(self, **kwargs):
            return {"type": "create_entry", **kwargs}

    ce.ConfigFlow = ConfigFlow
    ce.OptionsFlow = OptionsFlow
    ce.ConfigFlowResult = dict
    const.CONF_HOST = "host"
    const.CONF_PASSWORD = "password"
    core.callback = lambda func: func
    aio.async_get_clientsession = lambda hass: None

    class Selector:
        def __init__(self, config=None):
            self.config = config

        def __call__(self, value):
            return value

    class NumberSelectorMode:
        BOX = "box"

    class NumberSelectorConfig:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    selector.BooleanSelector = Selector
    selector.NumberSelector = Selector
    selector.NumberSelectorConfig = NumberSelectorConfig
    selector.NumberSelectorMode = NumberSelectorMode


_install_ha_stubs()

from novatek_em12x import config_flow


def _keys(schema: vol.Schema) -> set[str]:
    return {key.schema for key in schema.schema}


def test_options_flow_builds_schema():
    flow = config_flow.NovatekEMOptionsFlow()
    flow.config_entry = SimpleNamespace(
        options={},
        data={"scan_interval": 30},
    )
    result = asyncio.run(flow.async_step_init(None))
    assert result["type"] == "form"
    keys = _keys(result["data_schema"])
    assert keys == {
        "scan_interval",
        "sync_time",
        "auto_on_enabled",
        "auto_on_delay",
        "auto_on_days",
        "auto_on_external",
        "auto_on_retry",
        "auto_on_horizon",
    }


def test_options_flow_accepts_defaults_submission():
    flow = config_flow.NovatekEMOptionsFlow()
    flow.config_entry = SimpleNamespace(options={}, data={})
    result = asyncio.run(
        flow.async_step_init(
            {
                "scan_interval": 30,
                "sync_time": True,
                "auto_on_enabled": False,
                "auto_on_delay": 10,
                "auto_on_days": 1,
                "auto_on_external": False,
                "auto_on_retry": 10,
                "auto_on_horizon": 1,
            }
        )
    )
    assert result["type"] == "create_entry"


def test_user_step_shows_form():
    flow = config_flow.NovatekEMConfigFlow()
    result = asyncio.run(flow.async_step_user(None))
    assert result["type"] == "form"
    assert _keys(result["data_schema"]) == {"host", "password"}
