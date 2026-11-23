"""Tests for journal parsing helpers."""

from __future__ import annotations

from novatek_em12x.journals import (
    fault_mask_changes,
    is_reboot,
    latest_timestamp,
    newer_than,
    parse_journal,
    parse_syslog,
)


def test_parse_syslog_sorts_and_filters():
    rows = [
        [300, "SYS: Started v34 [PORR=1]."],
        [100, "WIFI: STA Connected successfully."],
        ["bad", "x"],
        [200],
    ]
    records = parse_syslog(rows)
    assert [r["timestamp"] for r in records] == [100, 300]
    assert is_reboot(records[1])
    assert not is_reboot(records[0])
    assert [r["timestamp"] for r in newer_than(records, 100)] == [300]
    assert latest_timestamp(records) == 300


def test_parse_journal_scaling():
    rows = [
        [500, 1544749712, 0, 2300, 0, 0, 312, 0],
        [200, 1544749184, 2, 2289, 150, 65, 256, 1234],
    ]
    records = parse_journal(rows)
    assert [r["timestamp"] for r in records] == [200, 500]
    first = records[0]
    assert first["voltage"] == 228.9
    assert first["power"] == 150.0
    assert first["current"] == 0.65
    assert first["temperature"] == 25.6
    assert first["energy_wh"] == 1234.0
    assert first["faul_flags"] == 2


def test_fault_mask_changes():
    records = [
        {"timestamp": 10, "faul_flags": 0},
        {"timestamp": 20, "faul_flags": 2},
        {"timestamp": 30, "faul_flags": 2},
        {"timestamp": 40, "faul_flags": 16},
        {"timestamp": 50, "faul_flags": 0},
    ]
    changes = fault_mask_changes(records)
    assert [(c["timestamp"], c["raised"]) for c in changes] == [(20, 2), (40, 16)]
    assert [c["raised"] for c in fault_mask_changes(records, previous_mask=2)] == [2, 16]


def test_relay_transitions():
    from novatek_em12x.journals import relay_transitions

    recs = [
        {"timestamp": 10, "sys_flags": 0x10},
        {"timestamp": 20, "sys_flags": 0x10},
        {"timestamp": 30, "sys_flags": 0x00},
        {"timestamp": 40, "sys_flags": 0x10},
    ]
    assert relay_transitions(recs, None) == []
    assert relay_transitions(recs, True) == [
        {"timestamp": 30, "relay": False},
        {"timestamp": 40, "relay": True},
    ]
    assert relay_transitions(recs, False) == [
        {"timestamp": 10, "relay": True},
        {"timestamp": 30, "relay": False},
        {"timestamp": 40, "relay": True},
    ]
