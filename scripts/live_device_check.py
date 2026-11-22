"""Live hardware test for the EM-129 against the real device.

Usage: python scripts/live_device_check.py <stage>
Stages: read | write_same | write_change | actions | events | reboot
"""

from __future__ import annotations

import asyncio
import sys
import time
import types
from pathlib import Path

from aiohttp import ClientSession, TCPConnector

PKG_DIR = Path(__file__).parent.parent / "custom_components" / "novatek_em12x"
pkg = types.ModuleType("novatek_em12x")
pkg.__path__ = [str(PKG_DIR)]
sys.modules.setdefault("novatek_em12x", pkg)

from novatek_em12x.api import EMApiClient, EMApiStatusError, EMError

HOST = "192.168.75.242"
PASSWORD = ""

READ_PARAMS = [
    "volt_msr", "cur_msr", "powa_msr", "pows_msr", "freq_msr", "tempr_msr",
    "enrga_msr", "enrgs_msr", "enrga_d_msr", "enrga_w_msr", "enrga_m_msr",
    "sys_flag", "faul_flag", "ar_time", "time",
    "volt_leveloff_hi", "volt_leveloff_lo", "volt_level_hys",
    "volt_timeoff_hi", "volt_timeoff_lo", "volt_timeon_apv", "volt_count_apv",
    "cur_leveloff", "cur_timeoff", "cur_timeon_apv", "cur_count_apv",
    "pow_enable", "pow_leveloff", "pow_timeoff", "pow_timeon_apv", "pow_count_apv",
    "freq_enable", "freq_leveloff_hi", "freq_leveloff_lo",
    "freq_timeoff", "freq_timeon_apv", "freq_count_apv",
    "hctrl_enable", "hctrl_from", "hctrl_to",
    "time_gmt", "time_corr", "dst_enable",
    "lock_panel_time", "on_time_limit", "apv_reset_time",
    "sync_sntp_enable", "sync_sntp_address", "sync_sntp_port", "sync_sntp_time",
    "led_intens", "cost_energy", "cost_unit",
    "user_info", "dev_passw", "device_mac", "device_ip",
]

NETWORK_PARAMS = {"wifi_ssid", "wifi_passw", "wifi_dhcp_enable", "wifi_ip", "wifi_gw", "wifi_mask", "dns1", "dns2"}

SAME_WRITE_PARAMS = [
    "volt_leveloff_hi", "volt_leveloff_lo", "volt_level_hys",
    "volt_timeoff_hi", "volt_timeoff_lo", "volt_timeon_apv", "volt_count_apv",
    "cur_leveloff", "cur_timeoff", "cur_timeon_apv", "cur_count_apv",
    "pow_enable", "pow_leveloff", "pow_timeoff", "pow_timeon_apv", "pow_count_apv",
    "freq_enable", "freq_leveloff_hi", "freq_leveloff_lo",
    "freq_timeoff", "freq_timeon_apv", "freq_count_apv",
    "hctrl_enable", "hctrl_from", "hctrl_to",
    "time_gmt", "time_corr", "dst_enable",
    "lock_panel_time", "on_time_limit", "apv_reset_time",
    "sync_sntp_enable", "sync_sntp_address", "sync_sntp_port", "sync_sntp_time",
    "led_intens", "cost_energy", "cost_unit",
]


async def make_client(session):
    return EMApiClient(HOST, PASSWORD, session)


def relay_on(sys_flag) -> bool:
    return bool(int(sys_flag) >> 4 & 1)


async def stage_read(client):
    print("=== STAGE: read all params ===")
    for param in READ_PARAMS:
        try:
            value = await client.get(param)
            print(f"  {param:24} = {value}")
        except EMError as err:
            print(f"  {param:24} !! {err}")
    info = await client.device_info()
    print(f"  device_info              = {info}")


async def stage_write_same(client):
    print("=== STAGE: write same values back ===")
    ok = fail = 0
    for param in SAME_WRITE_PARAMS:
        value = await client.get(param)
        try:
            await client.set_setting(param, value)
            back = await client.get(param)
            match = str(back) == str(value)
            ok += match
            fail += not match
            flag = "OK " if match else "DIFF"
            print(f"  {flag} {param:24} {value} -> {back}")
        except EMError as err:
            fail += 1
            print(f"  ERR {param:24} {value} !! {err}")
    print(f"  summary: ok={ok} fail={fail}")
    print("  -- user_info via base64 --")
    await client.set_setting("user_info", "RU0tMTI5")
    print("  user_info write:", await client.get("user_info"))
    print("  -- dev_passw empty --")
    try:
        await client.set_setting("dev_passw", "")
        print("  dev_passw '' ->", await client.get("dev_passw"))
    except EMError as err:
        print("  dev_passw '' !!", err)


async def roundtrip(client, param, new_value):
    old = await client.get(param)
    await client.set_setting(param, new_value)
    got = await client.get(param)
    await client.set_setting(param, old)
    restored = await client.get(param)
    print(f"  {param:24} {old} -> {new_value} -> read {got} -> restore {restored}")
    return got == new_value and restored == old


async def stage_write_change(client):
    print("=== STAGE: real value changes (round trip) ===")
    results = [
        await roundtrip(client, "led_intens", 7),
        await roundtrip(client, "cur_leveloff", 640),
        await roundtrip(client, "freq_leveloff_hi", 5150),
        await roundtrip(client, "volt_leveloff_hi", 260),
        await roundtrip(client, "cost_energy", 1500),
        await roundtrip(client, "time_gmt", 7200),
    ]
    print("  all round trips OK:", all(results))
    try:
        await client.set_setting("led_intens", 99)
        print("  out-of-range write led_intens=99: NO ERROR (unexpected)")
    except EMApiStatusError as err:
        print(f"  out-of-range write led_intens=99 rejected: {err.status}")


async def stage_actions(client):
    print("=== STAGE: actions ===")
    flag = await client.get("sys_flag")
    print(f"  relay initial: {'ON' if relay_on(flag) else 'OFF'} (sys_flag={flag})")
    await client.ctrl(False)
    flag = await client.get("sys_flag")
    print(f"  after ctrl off: {'ON' if relay_on(flag) else 'OFF'}")
    await asyncio.sleep(2)
    await client.ctrl(True)
    flag = await client.get("sys_flag")
    print(f"  after ctrl on:  {'ON' if relay_on(flag) else 'OFF'}")
    print("  -- energy reset --")
    try:
        await client.energy_reset()
        print("  enrgrst: OK, enrga:", await client.get("enrga_msr"))
    except EMError as err:
        print("  enrgrst !!", err)
    print("  -- clock/set --")
    before = int(str(await client.get("time")).split()[0])
    now = int(time.time())
    await client.set_clock(now)
    after = int(str(await client.get("time")).split()[0])
    print(f"  local now={now} device before={before} (drift {before - now}s) after={after} (drift {after - now}s)")
    print("  -- clock/sync (needs sntp enabled) --")
    sntp = await client.get("sync_sntp_enable")
    if not int(sntp):
        await client.set_setting("sync_sntp_enable", 1)
    try:
        await client.sync_clock()
        print("  clock/sync: OK")
    except EMError as err:
        print(f"  clock/sync !! {err}")
    if not int(sntp):
        await client.set_setting("sync_sntp_enable", 0)
        print(f"  sync_sntp_enable restored to {sntp}")


async def stage_events(client):
    print("=== STAGE: events and journals ===")
    ts = int(time.time()) + 3600
    url_ok = 0
    try:
        await client._sid_request(f"/api/event/set?time={ts}&repeat=3&live=60&flags=0&value=1")
        url_ok += 1
        print(f"  event/set: OK (time={ts} repeat=3 live=60)")
    except EMError as err:
        print(f"  event/set !! {err}")
    try:
        data = await client._sid_request("/api/event/get?offset=0")
        print(f"  event/get: {data}")
    except EMError as err:
        print(f"  event/get !! {err}")
    try:
        await client._sid_request(f"/api/event/set?time={ts}&repeat=3&live=60&flags=0&value=1")
        print("  duplicate event/set: NO ERROR (unexpected)")
    except EMApiStatusError as err:
        print(f"  duplicate event/set rejected: {err.status}")
    try:
        await client._sid_request("/api/event/delall")
        data = await client._sid_request("/api/event/get?offset=0")
        print(f"  event/delall: OK, after: {data}")
    except EMError as err:
        print(f"  event/delall !! {err}")
    print("  -- loger --")
    before = await client._sid_request("/api/loger/get?offset=0")
    print(f"  loger/get before: {len(before.get('LOGS', []))} records, status {before.get('STATUS')}")
    await client._sid_request("/api/loger/delall")
    after = await client._sid_request("/api/loger/get?offset=0")
    print(f"  loger/get after delall: {len(after.get('LOGS', []))} records, status {after.get('STATUS')}")
    print("  -- syslog --")
    before = await client._sid_request("/api/syslog/get?offset=0")
    print(f"  syslog/get before: {len(before.get('SYSLOGS', []))} records, status {before.get('STATUS')}")
    await client._sid_request("/api/syslog/delall")
    after = await client._sid_request("/api/syslog/get?offset=0")
    print(f"  syslog/get after delall: {len(after.get('SYSLOGS', []))} records, status {after.get('STATUS')}")


async def stage_reboot(client):
    print("=== STAGE: reboot ===")
    await client.reboot()
    print("  reboot command sent, waiting for device to come back...")
    deadline = time.monotonic() + 180
    session = client._session
    while time.monotonic() < deadline:
        await asyncio.sleep(5)
        probe = EMApiClient(HOST, PASSWORD, session)
        try:
            info = await probe.device_info()
            print(f"  device is back: {info}")
            salt_ok = await probe.get("volt_msr")
            print(f"  post-reboot login + read works, volt_msr={salt_ok}")
            await probe.close()
            return
        except EMError as err:
            print(f"  still down: {err}")
    print("  !! device did not come back in 180s")


STAGES = {
    "read": stage_read,
    "write_same": stage_write_same,
    "write_change": stage_write_change,
    "actions": stage_actions,
    "events": stage_events,
    "reboot": stage_reboot,
}


async def main():
    stage = sys.argv[1] if len(sys.argv) > 1 else "read"
    async with ClientSession(connector=TCPConnector(force_close=True)) as session:
        client = await make_client(session)
        await STAGES[stage](client)
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
