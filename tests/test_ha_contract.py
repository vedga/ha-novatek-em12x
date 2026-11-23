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
    "SensorDeviceClass.ENUM",
    "SensorDeviceClass.FREQUENCY",
    "SensorDeviceClass.MONETARY",
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


def test_unit_property_has_no_value_branches():
    from pathlib import Path

    src = Path("custom_components/novatek_em12x/sensor.py").read_text()
    block = src.split("def native_unit_of_measurement")[1].split("def device_class")[0]
    for forbidden in ("billing.reading", "last_syslog", "auto_on.deadline", "journal_missed"):
        assert forbidden not in block, forbidden


def test_options_flow_constructed_without_arguments():
    from pathlib import Path

    src = Path("custom_components/novatek_em12x/config_flow.py").read_text()
    assert "NovatekEMOptionsFlow(config_entry)" not in src
    assert "return NovatekEMOptionsFlow()" in src


def test_no_overlong_mapping_get_calls():
    import ast
    from pathlib import Path

    tree = ast.parse(
        Path("custom_components/novatek_em12x/config_flow.py").read_text()
    )
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and len(node.args) > 2
        ):
            raise AssertionError(
                f"Mapping.get with {len(node.args)} arguments at line {node.lineno}"
            )


def test_options_schema_matches_translations():
    import ast
    import json
    from pathlib import Path

    src = Path("custom_components/novatek_em12x/config_flow.py").read_text()
    tree = ast.parse(src)
    keys = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "Required"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "vol"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            keys.add(node.args[0].value)

    strings = json.loads(
        Path("custom_components/novatek_em12x/strings.json").read_text()
    )
    translated = set(strings["options"]["step"]["init"]["data"])
    missing = keys - translated
    assert not missing, f"options schema keys without translations: {missing}"


def test_voluptuous_keyword_args_are_single():
    import ast
    from pathlib import Path

    tree = ast.parse(
        Path("custom_components/novatek_em12x/config_flow.py").read_text()
    )
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in ("Required", "Optional")
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "vol"
            and len(node.args) > 1
        ):
            raise AssertionError(
                f"vol.{node.func.attr} with {len(node.args)} positional args "
                f"at line {node.lineno}"
            )
