"""Number platform for Novatek Electro EM settings."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.helpers.entity import EntityCategory

from .api import EMError
from .coordinator import NovatekEMCoordinator
from .entity import NovatekEMEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class NumberSpec:
    param: str
    min_value: float
    max_value: float
    step: float
    unit: str | None
    to_device: float
    from_device: float
    enabled_by: str | None = None


NUMBER_SPECS: dict[str, NumberSpec] = {
    "volt_leveloff_hi": NumberSpec("volt_leveloff_hi", 230, 290, 1, UnitOfElectricPotential.VOLT, 1, 1),
    "volt_leveloff_lo": NumberSpec("volt_leveloff_lo", 100, 220, 1, UnitOfElectricPotential.VOLT, 1, 1),
    "volt_level_hys": NumberSpec("volt_level_hys", 0, 20, 1, UnitOfElectricPotential.VOLT, 1, 1),
    "volt_timeoff_hi": NumberSpec("volt_timeoff_hi", 0.2, 2.0, 0.1, UnitOfTime.SECONDS, 0.001, 1000),
    "volt_timeoff_lo": NumberSpec("volt_timeoff_lo", 0.2, 60.0, 0.1, UnitOfTime.SECONDS, 0.001, 1000),
    "volt_timeon_apv": NumberSpec("volt_timeon_apv", 0.2, 600.0, 0.1, UnitOfTime.SECONDS, 0.001, 1000),
    "cur_leveloff": NumberSpec("cur_leveloff", 10, 160, 0.1, UnitOfElectricCurrent.AMPERE, 10, 0.1),
    "cur_timeoff": NumberSpec("cur_timeoff", 0.2, 10.0, 0.1, UnitOfTime.SECONDS, 0.001, 1000),
    "cur_timeon_apv": NumberSpec("cur_timeon_apv", 0.5, 600.0, 0.1, UnitOfTime.SECONDS, 0.001, 1000),
    "pow_leveloff": NumberSpec("pow_leveloff", 100, 3680, 10, UnitOfPower.WATT, 1, 1),
    "pow_timeoff": NumberSpec("pow_timeoff", 0.2, 10.0, 0.1, UnitOfTime.SECONDS, 0.001, 1000),
    "pow_timeon_apv": NumberSpec("pow_timeon_apv", 0.5, 600.0, 0.1, UnitOfTime.SECONDS, 0.001, 1000),
    "freq_leveloff_hi": NumberSpec("freq_leveloff_hi", 50, 65, 0.01, UnitOfFrequency.HERTZ, 100, 0.01),
    "freq_leveloff_lo": NumberSpec("freq_leveloff_lo", 45, 50, 0.01, UnitOfFrequency.HERTZ, 100, 0.01),
    "freq_timeoff": NumberSpec("freq_timeoff", 0.2, 10.0, 0.1, UnitOfTime.SECONDS, 0.001, 1000),
    "freq_timeon_apv": NumberSpec("freq_timeon_apv", 0.2, 600.0, 0.1, UnitOfTime.SECONDS, 0.001, 1000),
    "apv_reset_time": NumberSpec("apv_reset_time", 1, 60, 1, UnitOfTime.MINUTES, 60000, 1 / 60000),
    "on_time_limit": NumberSpec("on_time_limit", 0, 60, 1, UnitOfTime.MINUTES, 60000, 1 / 60000),
    "lock_panel_time": NumberSpec("lock_panel_time", 0, 10, 1, UnitOfTime.MINUTES, 60000, 1 / 60000),
    "time_corr": NumberSpec("time_corr", -9.9, 9.9, 0.1, UnitOfTime.SECONDS, 10, 0.1),
    "led_intens": NumberSpec("led_intens", 1, 15, 1, None, 1, 1),
    "cost_energy": NumberSpec("cost_energy", 0.001, 9999.999, 0.001, None, 1000, 0.001),
    "sync_sntp_port": NumberSpec("sync_sntp_port", 1, 65535, 1, None, 1, 1),
    "sync_sntp_time": NumberSpec("sync_sntp_time", 1, 24, 1, UnitOfTime.HOURS, 3600000, 1 / 3600000),
    "cloud_port": NumberSpec("cloud_port", 1, 65535, 1, None, 1, 1, "cloud_enable"),
}

async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator = entry.runtime_data.coordinator
    entities: list[NumberEntity] = [
        NovatekEMNumberEntity(coordinator, param, spec)
        for param, spec in NUMBER_SPECS.items()
    ]
    entities.append(NovatekEMBillingNumber(coordinator))
    async_add_entities(entities)


class NovatekEMNumberEntity(NovatekEMEntity, NumberEntity):
    """Numeric setting of the meter."""

    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: NovatekEMCoordinator,
        param: str,
        spec: NumberSpec,
    ) -> None:
        super().__init__(coordinator, f"number_{param}")
        self._param = param
        self._spec = spec
        self._attr_translation_key = param
        self._attr_native_min_value = spec.min_value
        self._attr_native_max_value = spec.max_value
        self._attr_native_step = spec.step
        self._attr_native_unit_of_measurement = spec.unit

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        if self._spec.enabled_by is not None:
            return bool(
                int(self.coordinator.data.settings.get(self._spec.enabled_by, 0) or 0)
            )
        return True

    @property
    def native_value(self) -> float | None:
        value = self.coordinator.data.settings.get(self._param)
        if value is None:
            return None
        try:
            return round(float(value) * self._spec.from_device, 4)
        except (TypeError, ValueError):
            return None

    async def async_set_native_value(self, value: float) -> None:
        client = self.coordinator.entry.runtime_data.client
        device_value = round(value * self._spec.to_device)
        _LOGGER.debug("Number %s -> %s (%s)", self._param, value, device_value)
        try:
            await client.set_setting(self._param, device_value)
        except EMError as err:
            _LOGGER.error("Failed to set %s: %s", self._param, err)
            await self.coordinator.async_request_refresh()
            return
        if self.coordinator.data:
            self.coordinator.data.settings[self._param] = device_value
            self.coordinator.async_update_listeners()


class NovatekEMBillingNumber(NovatekEMEntity, NumberEntity):
    """External (billing) meter reading setter / correction."""

    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 0
    _attr_native_max_value = 9_999_999.999
    _attr_native_step = 0.001
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_translation_key = "external_meter_set"
    _attr_icon = "mdi:counter"

    def __init__(self, coordinator: NovatekEMCoordinator) -> None:
        super().__init__(coordinator, "number_external_meter_set")

    @property
    def native_value(self) -> float | None:
        return self.coordinator.billing.reading

    async def async_set_native_value(self, value: float) -> None:
        measurements = self.coordinator.data.measurements if self.coordinator.data else {}
        device_wh = measurements.get("enrga_msr")
        if device_wh is None:
            device_wh = self.coordinator.billing.last_device_wh or 0
        await self.coordinator.billing.async_set_reading(value, int(device_wh))
