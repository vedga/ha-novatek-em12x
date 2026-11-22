"""Config flow for Novatek Electro EM."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import EMApiClient, EMAuthError, EMError, decode_setting_str
from .const import (
    CONF_SYNC_TIME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    MODEL_NAMES,
)

if TYPE_CHECKING:
    from . import NovatekEMConfigEntry

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PASSWORD, default=""): str,
    }
)


class NovatekEMConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Novatek EM."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            client = EMApiClient(
                user_input[CONF_HOST], user_input.get(CONF_PASSWORD, ""), session
            )
            try:
                info = await client.device_info()
                device_name = decode_setting_str(str(info.get("user_info", "")))
                model = MODEL_NAMES.get(info.get("device_id"))
                if not model:
                    _LOGGER.warning(
                        "Unknown device_id %s at %s",
                        info.get("device_id"),
                        user_input[CONF_HOST],
                    )
                mac = str(await client.get("device_mac"))
                sw_version: str | None = None
                try:
                    fw = await client.fwinfo()
                    sw_version = str(fw.get("CUR_VERSION")) or None
                except EMError:
                    _LOGGER.debug("fwinfo not supported")
            except EMAuthError:
                errors["base"] = "invalid_auth"
            except EMError as err:
                errors["base"] = "cannot_connect"
                _LOGGER.warning("Connection failed: %s", err)
            else:
                await client.close()
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_configured()
                title = device_name or model or "Novatek EM"
                return self.async_create_entry(
                    title=title,
                    data={
                        **user_input,
                        "mac": mac,
                        "device_id": info.get("device_id"),
                        "name": title,
                        "sw_version": sw_version,
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: NovatekEMConfigEntry,
    ) -> NovatekEMOptionsFlow:
        return NovatekEMOptionsFlow(config_entry)


class NovatekEMOptionsFlow(OptionsFlow):
    """Handle options for the Novatek EM integration."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if not MIN_SCAN_INTERVAL <= user_input["scan_interval"] <= MAX_SCAN_INTERVAL:
                errors["scan_interval"] = "invalid_interval"
            else:
                new_password = user_input.pop(CONF_PASSWORD, None)
                if new_password:
                    self.hass.config_entries.async_update_entry(
                        self.config_entry,
                        data={
                            **self.config_entry.data,
                            CONF_PASSWORD: new_password,
                        },
                    )
                return self.async_create_entry(title="", data=user_input)

        current_interval = self.config_entry.options.get(
            "scan_interval",
            self.config_entry.data.get("scan_interval", DEFAULT_SCAN_INTERVAL),
        )
        current_sync = self.config_entry.options.get(
            CONF_SYNC_TIME,
            self.config_entry.data.get(CONF_SYNC_TIME, True),
        )
        schema = vol.Schema(
            {
                vol.Required(
                    "scan_interval", default=int(current_interval)
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_SCAN_INTERVAL,
                        max=MAX_SCAN_INTERVAL,
                        step=1,
                        unit_of_measurement="s",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(CONF_SYNC_TIME, default=current_sync): BooleanSelector(),
                vol.Optional(CONF_PASSWORD): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
