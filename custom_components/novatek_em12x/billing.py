"""Pure helpers for the external (billing) meter reading."""

from __future__ import annotations

from itertools import pairwise
from typing import Any


def compute_reading(
    base_kwh: float,
    device_wh_at_base: int,
    device_wh_now: int,
    self_power_w: float = 0.0,
    calibration_pct: float = 0.0,
    base_ts: float | None = None,
    now_ts: float | None = None,
) -> float:
    """Return the external meter reading in kWh.

    The reading grows with the device energy counter (optionally scaled by the
    calibration factor) and with the elapsed time since the base point (the
    device self-consumption, which the device cannot measure itself).
    """
    delta_wh = int(device_wh_now) - int(device_wh_at_base)
    total = float(base_kwh) + delta_wh / 1000 * (1 + calibration_pct / 100)
    if base_ts is not None and now_ts is not None:
        elapsed_h = max(0.0, float(now_ts) - float(base_ts)) / 3600
        total += float(self_power_w) * elapsed_h / 1000
    return round(total, 3)


def should_rebase(last_device_wh: int | None, device_wh_now: int) -> bool:
    """Detect a device counter reset (the counter can only grow otherwise)."""
    if last_device_wh is None:
        return False
    return int(device_wh_now) < int(last_device_wh)


def fit_coefficients(
    history: list[dict[str, Any]],
    min_intervals: int = 3,
) -> dict[str, float | None] | None:
    """Fit the self-consumption power and the counter scale factor.

    The model for every interval between two correction points is
    ``dC_wh = self_power_w * dt_h + scale * dE_wh``. Returns a dict with
    ``self_power_w`` and ``scale`` (either may be ``None`` when not
    identifiable from the data) or ``None`` when there is not enough data.
    """
    intervals: list[tuple[float, float, float]] = []  # (dt_h, dE_wh, dC_wh)
    for prev, cur in pairwise(history):
        dt_h = (float(cur["ts"]) - float(prev["ts"])) / 3600
        d_e_wh = float(cur["device_wh"]) - float(prev["device_wh"])
        d_c_wh = (float(cur["kwh"]) - float(prev["kwh"])) * 1000
        if dt_h <= 0 or d_e_wh < 0 or d_c_wh < -50:
            continue
        intervals.append((dt_h, d_e_wh, d_c_wh))
    if len(intervals) < min_intervals:
        return None

    s_tt = sum(dt * dt for dt, _, _ in intervals)
    s_ee = sum(de * de for _, de, _ in intervals)
    s_te = sum(dt * de for dt, de, _ in intervals)
    s_tc = sum(dt * dc for dt, _, dc in intervals)
    s_ec = sum(de * dc for _, de, dc in intervals)

    if s_ee == 0:
        # No load energy at all: only the self-consumption is identifiable.
        return {"self_power_w": s_tc / s_tt, "scale": None}

    m_det = s_tt * s_ee - s_te * s_te
    if m_det <= 1e-3 * s_tt * s_ee:
        # Time and energy are proportional (constant load): inseparable.
        return {"self_power_w": None, "scale": None}

    # Solve the 2x2 normal equations:
    # [ s_tt  s_te ] [a]   [s_tc]
    # [ s_te  s_ee ] [b] = [s_ec]
    a = (s_tc * s_ee - s_ec * s_te) / m_det
    b = (s_tt * s_ec - s_te * s_tc) / m_det
    return {"self_power_w": a, "scale": b}
