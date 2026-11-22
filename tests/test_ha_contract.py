"""Guard against typos in Home Assistant enum members."""

from __future__ import annotations

HA_ENUM_WHITELIST = {
    "BinarySensorDeviceClass.PROBLEM",
    "EntityCategory.CONFIG",
    "EntityCategory.DIAGNOSTIC",
    "NumberMode.BOX",
    "SensorDeviceClass.APPARENT_POWER",
    "SensorDeviceClass.CURRENT",
    "SensorDeviceClass.ENERGY",
    "SensorDeviceClass.FREQUENCY",
    "SensorDeviceClass.POWER",
    "SensorDeviceClass.POWER_FACTOR",
    "SensorDeviceClass.TEMPERATURE",
    "SensorDeviceClass.TIMESTAMP",
    "SensorDeviceClass.VOLTAGE",
    "SensorStateClass.MEASUREMENT",
    "SensorStateClass.TOTAL",
    "SensorStateClass.TOTAL_INCREASING",
    "TextMode.TEXT",
    "UnitOfApparentPower.VOLT_AMPERE",
    "UnitOfElectricCurrent.AMPERE",
    "UnitOfElectricPotential.VOLT",
    "UnitOfEnergy.KILO_WATT_HOUR",
    "UnitOfFrequency.HERTZ",
    "UnitOfPower.WATT",
    "UnitOfTemperature.CELSIUS",
    "UnitOfTime.HOURS",
    "UnitOfTime.MINUTES",
    "UnitOfTime.SECONDS",
}


def test_ha_enum_attributes_are_known():
    import re
    from pathlib import Path

    pattern = re.compile(
        r"(SensorDeviceClass|SensorStateClass|BinarySensorDeviceClass|NumberMode|"
        r"TextMode|EntityCategory|UnitOf[A-Za-z]+)\.[A-Z_]+"
    )
    used = set()
    for path in Path("custom_components/novatek_em12x").glob("*.py"):
        used.update(pattern.findall(path.read_text()))
        for match in pattern.finditer(path.read_text()):
            used.add(match.group(0))
    used = {u for u in used if "." in u}
    unknown = used - HA_ENUM_WHITELIST
    assert not unknown, f"Unknown HA enum members: {unknown}"
