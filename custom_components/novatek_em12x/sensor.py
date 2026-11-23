"""Sensor platform for Novatek Electro EM."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.util import dt as dt_util

from .const import (
    ISO_CURRENCIES,
    STATUS_CLOUD_SYNCED_BIT,
    STATUS_NTP_SYNCED_BIT,
    currency_code,
    energy_cost,
    tariff_value,
)
from .coordinator import NovatekEMCoordinator
from .entity import NovatekEMEntity


def _pf(measurements: dict[str, Any]) -> float | None:
    apparent = measurements.get("pows_msr")
    active = measurements.get("powa_msr")
    if not apparent or active is None:
        return None
    return round(max(0.0, min(1.0, active / apparent)), 3)


SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="volt_msr",
        translation_key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="cur_msr",
        translation_key="current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="powa_msr",
        translation_key="active_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="pows_msr",
        translation_key="apparent_power",
        device_class=SensorDeviceClass.APPARENT_POWER,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="power_factor",
        translation_key="power_factor",
        device_class=SensorDeviceClass.POWER_FACTOR,
        native_unit_of_measurement=None,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    SensorEntityDescription(
        key="freq_msr",
        translation_key="frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="tempr_msr",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="enrga_msr",
        translation_key="energy_active",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=3,
    ),
    SensorEntityDescription(
        key="enrgs_msr",
        translation_key="energy_apparent",
        device_class=None,
        native_unit_of_measurement="kVAh",
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=3,
    ),
    SensorEntityDescription(
        key="enrga_d_msr",
        translation_key="energy_active_daily",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=3,
    ),
    SensorEntityDescription(
        key="enrga_w_msr",
        translation_key="energy_active_weekly",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=3,
    ),
    SensorEntityDescription(
        key="enrga_m_msr",
        translation_key="energy_active_monthly",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=3,
    ),
    SensorEntityDescription(
        key="ar_time",
        translation_key="reclose_countdown",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:timer-outline",
    ),
    SensorEntityDescription(
        key="device_time",
        translation_key="device_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="ntp_synced",
        translation_key="ntp_synced",
        device_class=SensorDeviceClass.ENUM,
        options=["on", "off"],
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:check-network",
    ),
    SensorEntityDescription(
        key="cloud_synced",
        translation_key="cloud_synced",
        device_class=SensorDeviceClass.ENUM,
        options=["on", "off"],
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:cloud-check-outline",
    ),
    SensorEntityDescription(
        key="cloud_status",
        translation_key="cloud_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:cloud-question",
    ),
    SensorEntityDescription(
        key="cloud_last_error",
        translation_key="cloud_last_error",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:cloud-alert",
    ),
    SensorEntityDescription(
        key="cloud_server",
        translation_key="cloud_server",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:server",
    ),
    SensorEntityDescription(
        key="last_event",
        translation_key="last_event",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:history",
    ),
    SensorEntityDescription(
        key="journal_missed",
        translation_key="journal_missed",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:database-arrow-down",
    ),
    SensorEntityDescription(
        key="auto_on_at",
        translation_key="auto_on_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:timer-lock-open-outline",
    ),
    SensorEntityDescription(
        key="external_meter",
        translation_key="external_meter",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=3,
        icon="mdi:counter",
    ),
    SensorEntityDescription(
        key="tariff",
        translation_key="tariff",
        icon="mdi:cash",
        suggested_display_precision=3,
    ),
    SensorEntityDescription(
        key="cost_total",
        translation_key="cost_total",
        icon="mdi:cash-multiple",
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="cost_daily",
        translation_key="cost_daily",
        icon="mdi:cash-clock",
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="cost_weekly",
        translation_key="cost_weekly",
        icon="mdi:cash-clock",
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="cost_monthly",
        translation_key="cost_monthly",
        icon="mdi:cash-clock",
        suggested_display_precision=2,
    ),
)

CLOUD_SENSORS = {
    "cloud_status": "STAT",
    "cloud_last_error": "LERR",
    "cloud_server": "SERV",
}

COST_COUNTERS = {
    "cost_total": "enrga_msr",
    "cost_daily": "enrga_d_msr",
    "cost_weekly": "enrga_w_msr",
    "cost_monthly": "enrga_m_msr",
}

SCALES = {
    "volt_msr": 0.1,
    "cur_msr": 0.01,
    "freq_msr": 0.01,
    "tempr_msr": 0.1,
    "enrga_msr": 0.001,
    "enrgs_msr": 0.001,
    "enrga_d_msr": 0.001,
    "enrga_w_msr": 0.001,
    "enrga_m_msr": 0.001,
    "ar_time": 1,
}


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        NovatekEMSensorEntity(coordinator, description) for description in SENSORS
    )


class NovatekEMSensorEntity(NovatekEMEntity, SensorEntity):
    """Sensor for Novatek EM measurements."""

    entity_description: SensorEntityDescription

    def __init__(
        self,
        coordinator: NovatekEMCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, f"sensor_{description.key}")
        self.entity_description = description

    @property
    def _currency(self) -> str | None:
        return currency_code(self.coordinator.data.settings.get("cost_unit", ""))

    @property
    def native_unit_of_measurement(self) -> str | None:
        key = self.entity_description.key
        if key == "last_event":
            record = self.coordinator.data.last_syslog
            if not record:
                return None
            return datetime.fromtimestamp(int(record["timestamp"]), tz=dt_util.UTC)
        if key == "external_meter":
            return self.coordinator.billing.reading
        if key == "auto_on_at":
            deadline = self.coordinator.auto_on.deadline
            if deadline is None:
                return None
            return datetime.fromtimestamp(int(deadline), tz=dt_util.UTC)
        if key == "journal_missed":
            return self.coordinator.data.journal_missed
        if key == "tariff":
            code = self._currency
            return f"{code}/kWh" if code else None
        if key in COST_COUNTERS:
            return self._currency
        return self.entity_description.native_unit_of_measurement

    @property
    def device_class(self) -> SensorDeviceClass | None:
        key = self.entity_description.key
        if key in COST_COUNTERS:
            code = self._currency
            return SensorDeviceClass.MONETARY if code in ISO_CURRENCIES else None
        return self.entity_description.device_class

    @property
    def state_class(self) -> SensorStateClass | None:
        key = self.entity_description.key
        if key in COST_COUNTERS:
            return (
                SensorStateClass.TOTAL
                if self._currency in ISO_CURRENCIES
                else None
            )
        return self.entity_description.state_class

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.key == "external_meter":
            billing = self.coordinator.billing
            return {
                "base_kwh": billing.base_kwh,
                "device_wh_at_base": billing.device_wh_at_base,
                "updated_at": billing.updated_at,
            }
        if self.entity_description.key == "last_event":
            record = self.coordinator.data.last_syslog
            if record:
                return {"message": record["message"]}
        return None

    @property
    def native_value(self) -> str | float | datetime | None:
        key = self.entity_description.key
        measurements = self.coordinator.data.measurements
        if key == "power_factor":
            return _pf(measurements)
        if key == "device_time":
            raw = str(measurements.get("time", "")).split()[0]
            if not raw.isdigit():
                return None
            try:
                gmt = int(self.coordinator.data.settings.get("time_gmt", 0))
            except (TypeError, ValueError):
                gmt = 0
            return datetime.fromtimestamp(int(raw) - gmt, tz=dt_util.UTC)
        if key == "ntp_synced":
            return (
                "on"
                if int(measurements.get("sys_flag", 0)) >> STATUS_NTP_SYNCED_BIT & 1
                else "off"
            )
        if key == "cloud_synced":
            return (
                "on"
                if int(measurements.get("sys_flag", 0)) >> STATUS_CLOUD_SYNCED_BIT & 1
                else "off"
            )
        if key in CLOUD_SENSORS:
            value = self.coordinator.data.cloud.get(CLOUD_SENSORS[key])
            if value is None:
                return None
            return str(value)
        if key == "last_event":
            record = self.coordinator.data.last_syslog
            if not record:
                return None
            return datetime.fromtimestamp(int(record["timestamp"]), tz=dt_util.UTC)
        if key == "external_meter":
            return self.coordinator.billing.reading
        if key == "auto_on_at":
            deadline = self.coordinator.auto_on.deadline
            if deadline is None:
                return None
            return datetime.fromtimestamp(int(deadline), tz=dt_util.UTC)
        if key == "journal_missed":
            return self.coordinator.data.journal_missed
        if key == "tariff":
            return tariff_value(self.coordinator.data.settings.get("cost_energy"))
        if key in COST_COUNTERS:
            return energy_cost(
                measurements.get(COST_COUNTERS[key]),
                self.coordinator.data.settings.get("cost_energy"),
            )
        value = measurements.get(key)
        if value is None:
            return None
        scale = SCALES.get(key)
        return round(value * scale, 4) if scale else value
