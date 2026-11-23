"""Pure helpers for the external (billing) meter reading."""

from __future__ import annotations


def compute_reading(
    base_kwh: float, device_wh_at_base: int, device_wh_now: int
) -> float:
    """Return the external meter reading in kWh."""
    delta_wh = int(device_wh_now) - int(device_wh_at_base)
    return round(float(base_kwh) + delta_wh / 1000, 3)


def should_rebase(last_device_wh: int | None, device_wh_now: int) -> bool:
    """Detect a device counter reset (the counter can only grow otherwise)."""
    if last_device_wh is None:
        return False
    return int(device_wh_now) < int(last_device_wh)
