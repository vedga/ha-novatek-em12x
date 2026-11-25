"""Tests for the external billing meter helpers."""

from __future__ import annotations

from novatek_em12x.billing import compute_reading, fit_coefficients, should_rebase


def test_compute_reading():
    assert compute_reading(100.0, 5000, 7000) == 102.0
    assert compute_reading(100.0, 5000, 5000) == 100.0
    assert compute_reading(100.123, 0, 1) == 100.124
    assert compute_reading(0.0, 1000, 0) == -1.0


def test_compute_reading_with_calibration_and_self_power():
    # 2 kWh counter delta scaled by +10 %
    assert compute_reading(100.0, 5000, 7000, 0.0, 10.0) == 102.2
    # 0.5 W over 10 hours = 0.005 kWh
    assert compute_reading(100.0, 5000, 5000, 0.5, 0.0, 0, 36000) == 100.005
    # both, negative elapsed time ignored
    assert compute_reading(100.0, 5000, 7000, 0.5, 10.0, 36000, 0) == 102.2


def test_should_rebase():
    assert should_rebase(7000, 5000) is True
    assert should_rebase(5000, 7000) is False
    assert should_rebase(None, 10) is False
    assert should_rebase(0, 0) is False


def _point(ts, wh, kwh):
    return {"ts": ts, "device_wh": wh, "kwh": kwh}


def test_fit_rejects_short_history():
    history = [_point(0, 0, 0), _point(3600, 100, 0.1)]
    assert fit_coefficients(history) is None


def test_fit_self_power_only():
    # No load energy: divergence is purely self-consumption (1 W => 0.001 kWh/h).
    history = [
        _point(0, 0, 100.0),
        _point(7200, 0, 100.002),
        _point(14400, 0, 100.004),
        _point(21600, 0, 100.006),
    ]
    fit = fit_coefficients(history)
    assert fit is not None
    assert abs(fit["self_power_w"] - 1.0) < 0.01
    assert fit["scale"] is None


def test_fit_calibration_only():
    # No self-consumption, load overcounts by 5 % with varying load.
    history = [
        _point(0, 0, 100.0),
        _point(3600, 1000, 101.05),
        _point(7200, 1500, 101.575),
        _point(10800, 3000, 103.15),
    ]
    fit = fit_coefficients(history)
    assert fit is not None
    assert abs(fit["scale"] - 1.05) < 0.001
    assert abs(fit["self_power_w"]) < 0.01


def test_fit_separates_both_parameters():
    # 1 W self-consumption and 2 % overcount with varying load.
    history = [
        _point(0, 0, 100.0),
        _point(3600, 1000, 101.021),
        _point(10800, 4000, 104.083),
        _point(18000, 5000, 105.105),
    ]
    fit = fit_coefficients(history)
    assert fit is not None
    assert abs(fit["self_power_w"] - 1.0) < 0.05
    assert abs(fit["scale"] - 1.02) < 0.001


def test_fit_collinear_data_is_inseparable():
    # Energy strictly proportional to time (constant load): no split possible.
    history = [
        _point(0, 0, 100.0),
        _point(3600, 1000, 101.001),
        _point(7200, 2000, 102.002),
        _point(10800, 3000, 103.003),
    ]
    fit = fit_coefficients(history)
    assert fit is not None
    assert fit["self_power_w"] is None
    assert fit["scale"] is None


def test_fit_skips_invalid_intervals():
    # The first interval has a device counter reset; it is skipped.
    history = [
        _point(0, 5000, 100.0),
        _point(3600, 200, 100.0),
        _point(10800, 1200, 101.001),
        _point(14400, 2200, 102.0015),
        _point(18000, 3200, 103.002),
    ]
    fit = fit_coefficients(history)
    assert fit is not None
    assert abs(fit["self_power_w"] - 0.5) < 0.05
    assert abs(fit["scale"] - 1.0) < 0.001
