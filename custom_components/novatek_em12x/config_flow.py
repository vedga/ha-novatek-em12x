"""Config flow for Novatek Electro EM."""

from __future__ import annotations

import logging
from dataclasses import dataclass
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
)

from .api import EMApiClient, EMAuthError, EMError, decode_setting_str
from .const import (
    CONF_AUTO_ON_DELAY,
    CONF_AUTO_ON_DURATION,
    CONF_AUTO_ON_ENABLED,
    CONF_AUTO_ON_EXTERNAL,
    CONF_AUTO_ON_HORIZON,
    CONF_AUTO_ON_RETRY,
    CONF_SYNC_TIME,
    DEFAULT_AUTO_ON_DELAY,
    DEFAULT_AUTO_ON_DURATION,
    DEFAULT_AUTO_ON_HORIZON,
    DEFAULT_AUTO_ON_RETRY,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_AUTO_ON_DELAY,
    MAX_AUTO_ON_DURATION,
    MAX_AUTO_ON_HORIZON,
    MAX_AUTO_ON_RETRY,
    MAX_SCAN_INTERVAL,
    MIN_AUTO_ON_DELAY,
    MIN_AUTO_ON_DURATION,
    MIN_AUTO_ON_HORIZON,
    MIN_AUTO_ON_RETRY,
    MIN_SCAN_INTERVAL,
    MODEL_NAMES,
)

if TYPE_CHECKING:
    from . import NovatekEMConfigEntry

_LOGGER = logging.getLogger(__name__)


@dataclass
class EMProbe:
    """Result of probing a device."""

    mac: str
    device_id: Any
    name: str
    model: str | None
    sw_version: str | None

    @property
    def title(self) -> str:
        return self.name or self.model or "Novatek EM"


async def async_probe_device(hass, host: str, password: str) -> EMProbe:
    """Connect to the device and read its identity."""
    client = EMApiClient(host, password, async_get_clientsession(hass))
    try:
        info = await client.device_info()
        name = decode_setting_str(str(info.get("user_info", "")))
        model = MODEL_NAMES.get(info.get("device_id"))
        if not model:
            _LOGGER.warning("Unknown device_id %s at %s", info.get("device_id"), host)
        mac = str(await client.get("device_mac"))
        sw_version: str | None = None
        try:
            fw = await client.fwinfo()
            sw_version = str(fw.get("CUR_VERSION")) or None
        except EMError:
            _LOGGER.debug("fwinfo not supported")
    finally:
        await client.close()
    return EMProbe(
        mac=mac,
        device_id=info.get("device_id"),
        name=name,
        model=model,
        sw_version=sw_version,
    )


class NovatekEMConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Novatek EM."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            probe, errors = await self._async_try_probe(user_input)
            if probe is not None:
                await self.async_set_unique_id(probe.mac)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=probe.title,
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PASSWORD: user_input.get(CONF_PASSWORD, ""),
                        "mac": probe.mac,
                        "device_id": probe.device_id,
                        "name": probe.title,
                        "sw_version": probe.sw_version,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_PASSWORD, default=""): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            probe, errors = await self._async_try_probe(user_input)
            if probe is not None:
                await self.async_set_unique_id(probe.mac)
                self._abort_if_unique_id_mismatch(reason="wrong_device")
                return self.async_update_reload_and_abort(
                    entry,
                    title=probe.title,
                    data_updates={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PASSWORD: user_input.get(CONF_PASSWORD, ""),
                        "device_id": probe.device_id,
                        "name": probe.title,
                        "sw_version": probe.sw_version,
                    },
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST, default=entry.data.get(CONF_HOST)
                    ): str,
                    vol.Optional(
                        CONF_PASSWORD,
                        default=entry.data.get(CONF_PASSWORD, ""),
                    ): str,
                }
            ),
            errors=errors,
            description_placeholders={"name": entry.title},
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            probe, errors = await self._async_try_probe(
                {
                    CONF_HOST: entry.data.get(CONF_HOST),
                    CONF_PASSWORD: user_input.get(CONF_PASSWORD, ""),
                }
            )
            if probe is not None:
                await self.async_set_unique_id(probe.mac)
                self._abort_if_unique_id_mismatch(reason="wrong_device")
                return self.async_update_reload_and_abort(
                    entry,
                    title=probe.title,
                    data_updates={
                        CONF_PASSWORD: user_input.get(CONF_PASSWORD, ""),
                        "device_id": probe.device_id,
                        "name": probe.title,
                        "sw_version": probe.sw_version,
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {vol.Optional(CONF_PASSWORD, default=""): str}
            ),
            errors=errors,
            description_placeholders={"name": entry.title},
        )

    async def _async_try_probe(
        self, user_input: dict[str, Any]
    ) -> tuple[EMProbe | None, dict[str, str]]:
        try:
            probe = await async_probe_device(
                self.hass,
                user_input[CONF_HOST],
                user_input.get(CONF_PASSWORD, ""),
            )
        except EMAuthError as err:
            _LOGGER.warning("Authentication failed: %s", err)
            return None, {"base": "invalid_auth"}
        except EMError as err:
            _LOGGER.warning("Connection failed: %s", err)
            return None, {"base": "cannot_connect"}
        return probe, {}

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
                return self.async_create_entry(title="", data=user_input)

        current_interval = self.config_entry.options.get(
            "scan_interval",
            self.config_entry.data.get("scan_interval", DEFAULT_SCAN_INTERVAL),
        )
        current_sync = self.config_entry.options.get(
            CONF_SYNC_TIME,
            self.config_entry.data.get(CONF_SYNC_TIME, True),
        )
        current_auto_on = self.config_entry.options.get(
            CONF_AUTO_ON_ENABLED,
    CONF_AUTO_ON_EXTERNAL,
    CONF_AUTO_ON_HORIZON,
    CONF_AUTO_ON_RETRY,
            self.config_entry.data.get(CONF_AUTO_ON_ENABLED, False),
        )
        current_delay = self.config_entry.options.get(
            CONF_AUTO_ON_DELAY,
            self.config_entry.data.get(CONF_AUTO_ON_DELAY, DEFAULT_AUTO_ON_DELAY),
        )
        current_duration = self.config_entry.options.get(
            CONF_AUTO_ON_DURATION,
            self.config_entry.data.get(
                CONF_AUTO_ON_DURATION, DEFAULT_AUTO_ON_DURATION
            ),
        )
        current_external = self.config_entry.options.get(
            CONF_AUTO_ON_EXTERNAL,
            self.config_entry.data.get(CONF_AUTO_ON_EXTERNAL, False),
        )
        current_retry = self.config_entry.options.get(
            CONF_AUTO_ON_RETRY,
            self.config_entry.data.get(CONF_AUTO_ON_RETRY, DEFAULT_AUTO_ON_RETRY),
        )
        current_horizon = self.config_entry.options.get(
            CONF_AUTO_ON_HORIZON,
            self.config_entry.data.get(
                CONF_AUTO_ON_HORIZON, DEFAULT_AUTO_ON_HORIZON
            ),
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
                vol.Required(
                    CONF_AUTO_ON_ENABLED,
    CONF_AUTO_ON_EXTERNAL,
    CONF_AUTO_ON_HORIZON,
    CONF_AUTO_ON_RETRY, default=current_auto_on
                ): BooleanSelector(),
                vol.Required(
                    CONF_AUTO_ON_DELAY, default=int(current_delay)
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_AUTO_ON_DELAY,
                        max=MAX_AUTO_ON_DELAY,
                        step=1,
                        unit_of_measurement="min",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_AUTO_ON_DURATION, default=int(current_duration)
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_AUTO_ON_DURATION,
                        max=MAX_AUTO_ON_DURATION,
                        step=1,
                        unit_of_measurement="h",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_AUTO_ON_EXTERNAL, default=current_external
                ): BooleanSelector(),
                vol.Required(
                    CONF_AUTO_ON_RETRY, default=int(current_retry)
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_AUTO_ON_RETRY,
                        max=MAX_AUTO_ON_RETRY,
                        step=1,
                        unit_of_measurement="min",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_AUTO_ON_HORIZON, default=int(current_horizon)
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_AUTO_ON_HORIZON,
                        max=MAX_AUTO_ON_HORIZON,
                        step=1,
                        unit_of_measurement="h",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
