"""Pure helpers for parsing device journals."""

from __future__ import annotations

from typing import Any


def parse_syslog(rows: list[list[Any]]) -> list[dict[str, Any]]:
    """Convert raw syslog rows to records sorted oldest first."""
    out = []
    for row in rows:
        if len(row) != 2:
            continue
        try:
            timestamp = int(row[0])
        except (TypeError, ValueError):
            continue
        out.append({"timestamp": timestamp, "message": str(row[1])})
    out.sort(key=lambda item: item["timestamp"])
    return out


def _scaled(value: Any, factor: float) -> float | None:
    try:
        return round(int(value) * factor, 2)
    except (TypeError, ValueError):
        return None


def parse_journal(rows: list[list[Any]]) -> list[dict[str, Any]]:
    """Convert raw data-log rows to records sorted oldest first."""
    out = []
    for row in rows:
        if len(row) != 8:
            continue
        try:
            timestamp = int(row[0])
            sys_flags = int(row[1])
            faul_flags = int(row[2])
        except (TypeError, ValueError):
            continue
        out.append(
            {
                "timestamp": timestamp,
                "sys_flags": sys_flags,
                "faul_flags": faul_flags,
                "voltage": _scaled(row[3], 0.1),
                "power": _scaled(row[4], 1.0),
                "current": _scaled(row[5], 0.01),
                "temperature": _scaled(row[6], 0.1),
                "energy_wh": _scaled(row[7], 1.0),
            }
        )
    out.sort(key=lambda item: item["timestamp"])
    return out


def newer_than(records: list[dict[str, Any]], since: int) -> list[dict[str, Any]]:
    """Return records strictly newer than the given timestamp."""
    return [record for record in records if record["timestamp"] > since]


def latest_timestamp(records: list[dict[str, Any]], default: int = 0) -> int:
    """Return the newest timestamp in the records."""
    return max((record["timestamp"] for record in records), default=default)


def fault_mask_changes(
    records: list[dict[str, Any]], previous_mask: int = 0
) -> list[dict[str, Any]]:
    """Return transitions where new fault bits appeared."""
    changes = []
    last = previous_mask
    for record in records:
        mask = record["faul_flags"]
        raised = mask & ~last
        if raised:
            changes.append(
                {"timestamp": record["timestamp"], "raised": raised, "mask": mask}
            )
        last = mask
    return changes


def is_reboot(record: dict[str, Any]) -> bool:
    """Return True if a syslog record reports a device start."""
    return record["message"].startswith("SYS: Started")


def relay_transitions(
    records: list[dict[str, Any]], previous_state: bool | None
) -> list[dict[str, Any]]:
    """Return records where the load relay state changed."""
    out = []
    last = previous_state
    for record in records:
        state = bool(record["sys_flags"] >> 4 & 1)
        if last is not None and state != last:
            out.append({"timestamp": record["timestamp"], "relay": state})
        last = state
    return out
