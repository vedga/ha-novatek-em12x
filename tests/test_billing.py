"""Tests for the external billing meter helpers."""

from __future__ import annotations

from novatek_em12x.billing import compute_reading, should_rebase


def test_compute_reading():
    assert compute_reading(100.0, 5000, 7000) == 102.0
    assert compute_reading(100.0, 5000, 5000) == 100.0
    assert compute_reading(100.123, 0, 1) == 100.124
    assert compute_reading(0.0, 1000, 0) == -1.0


def test_should_rebase():
    assert should_rebase(7000, 5000) is True
    assert should_rebase(5000, 7000) is False
    assert should_rebase(None, 10) is False
    assert should_rebase(0, 0) is False
