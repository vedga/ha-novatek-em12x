"""Tests for the Novatek EM API client."""

from __future__ import annotations

import pytest
from aiohttp import ClientSession, TCPConnector
from fake_device import PASSWORD, STATE, FakeDevice
from novatek_em12x.api import (
    EMApiClient,
    EMApiStatusError,
    EMAuthError,
    EMConnectionError,
    decode_setting_str,
    encode_setting_str,
)


@pytest.fixture
async def device():
    dev = FakeDevice()
    host = await dev.start()
    yield dev, host
    await dev.stop()


@pytest.fixture
async def session():
    s = ClientSession(connector=TCPConnector(force_close=True))
    yield s
    await s.close()


async def test_login_and_measurements(device, session):
    dev, host = device
    client = EMApiClient(host, PASSWORD, session)
    data = await client.get_many(("volt_msr", "cur_msr", "freq_msr", "tempr_msr"))
    assert data == {
        "volt_msr": 2287,
        "cur_msr": 512,
        "freq_msr": 4999,
        "tempr_msr": 246,
    }
    assert client._sid in dev.sids
    await client.close()
    assert client._sid not in dev.sids


async def test_wrong_password(device, session):
    _dev, host = device
    client = EMApiClient(host, "wrong", session)
    with pytest.raises(EMAuthError):
        await client.get("volt_msr")


async def test_relogin_on_expired_sid(device, session):
    dev, host = device
    client = EMApiClient(host, PASSWORD, session)
    await client.get("volt_msr")
    dev.expire_all_sids = True
    assert await client.get("volt_msr") == 2287


async def test_unknown_param_raises_status_error(device, session):
    _dev, host = device
    client = EMApiClient(host, PASSWORD, session)
    with pytest.raises(EMApiStatusError) as err:
        await client.get("volt_rms")
    assert err.value.status == "SINTAXIS_ERROR"


async def test_set_setting(device, session):
    _dev, host = device
    client = EMApiClient(host, PASSWORD, session)
    await client.set_setting("led_intens", 7)
    assert STATE["led_intens"] == "7"
    with pytest.raises(EMApiStatusError):
        await client.set_setting("unknown_param", 1)


async def test_ctrl_and_clock(device, session):
    _dev, host = device
    client = EMApiClient(host, PASSWORD, session)
    await client.ctrl(True)
    await client.ctrl(False)
    await client.set_clock(1795360000)
    await client.sync_clock()
    await client.energy_reset()
    await client.reboot()


async def test_connection_error(device, session):
    _dev, _host = device
    client = EMApiClient("127.0.0.1:1", PASSWORD, session)
    with pytest.raises(EMConnectionError):
        await client.get("volt_msr")


async def test_transient_http_failure_recovers(device, session):
    dev, host = device
    client = EMApiClient(host, PASSWORD, session)
    await client.get("volt_msr")
    dev.fail_next = True
    with pytest.raises(EMConnectionError):
        await client.get("volt_msr")
    assert await client.get("volt_msr") == 2287


async def test_requests_are_serialized(device, session):
    _dev, host = device
    client = EMApiClient(host, PASSWORD, session)
    results = [await client.get(p) for p in ("volt_msr", "cur_msr", "tempr_msr")]
    assert results == [2287, 512, 246]


def test_setting_str_codec():
    assert decode_setting_str("74696d652e77696e646f77732e636f6d") == "time.windows.com"
    assert decode_setting_str("454d2d313239") == "EM-129"
    assert decode_setting_str("") == ""
    assert decode_setting_str("not-hex!") == "not-hex!"
    assert encode_setting_str("ntp.local") == "6e74702e6c6f63616c"
    assert decode_setting_str(encode_setting_str("pool.ntp.org")) == "pool.ntp.org"


async def test_get_many_batches_into_one_request(device, session):
    _dev, host = device
    from fake_device import SERIALIZED_LOG

    SERIALIZED_LOG.clear()
    client = EMApiClient(host, PASSWORD, session)
    data = await client.get_many(("volt_msr", "cur_msr", "tempr_msr"))
    assert data == {"volt_msr": 2287, "cur_msr": 512, "tempr_msr": 246}
    api_calls = [p for p in SERIALIZED_LOG if "/api/" in p and "login" not in p]
    assert len(api_calls) == 1, api_calls
    await client.close()


async def test_get_many_fallback_on_bad_param(device, session):
    _dev, host = device
    client = EMApiClient(host, PASSWORD, session)
    data = await client.get_many(("volt_msr", "volt_rms"))
    assert data == {"volt_msr": 2287}
    await client.close()


async def test_set_many_atomic(device, session):
    _dev, host = device
    client = EMApiClient(host, PASSWORD, session)
    before = STATE["led_intens"]
    data = await client._sid_request("/api/settings/set?led_intens=5&unknown=1")
    assert data["STATUS"] == "SINTAXIS_ERROR"
    assert STATE["led_intens"] == before


async def test_fwinfo(device, session):
    _dev, host = device
    client = EMApiClient(host, PASSWORD, session)
    fw = await client.fwinfo()
    assert fw["CUR_VERSION"] == "1.271.3.34"
    await client.close()


async def test_cloud_info(device, session):
    _dev, host = device
    client = EMApiClient(host, PASSWORD, session)
    info = await client.cloud_info()
    assert info["SERV"] == "my.overvis.com"
    assert info["STAT"] == 4
    await client.close()


async def test_wifi_wdt_setting(device, session):
    _dev, host = device
    client = EMApiClient(host, PASSWORD, session)
    assert await client.get("wifi_wdt_enable") == 1
    await client.set_setting("wifi_wdt_enable", 0)
    assert await client.get("wifi_wdt_enable") == "0"
    await client.set_setting("wifi_wdt_enable", 1)
    await client.close()


async def test_relogin_after_reboot_redirect(device, session):
    dev, host = device
    client = EMApiClient(host, PASSWORD, session)
    assert await client.get("volt_msr") == 2287
    dev.sids.clear()
    assert await client.get("volt_msr") == 2287
    assert client._sid in dev.sids


async def test_batch_relogin_after_reboot(device, session):
    dev, host = device
    client = EMApiClient(host, PASSWORD, session)
    await client.get_many(("volt_msr", "cur_msr"))
    dev.sids.clear()
    data = await client.get_many(("volt_msr", "cur_msr", "tempr_msr"))
    assert data["volt_msr"] == 2287


def test_cost_helpers():
    from novatek_em12x.const import currency_code, energy_cost, tariff_value

    assert currency_code(13) == "RUB"
    assert currency_code(1) == "BGN"
    assert currency_code(99) is None
    assert currency_code(None) is None
    assert tariff_value(1000) == 1.0
    assert tariff_value(2500) == 2.5
    assert tariff_value(None) is None
    assert energy_cost(12345, 1000) == 12.345
    assert energy_cost(500, 2500) == 1.25
    assert energy_cost(None, 1000) is None
    assert energy_cost(1000, None) is None


async def test_cloud_address_and_port(device, session):
    _dev, host = device
    client = EMApiClient(host, PASSWORD, session)
    assert await client.get("cloud_address") == "6d792e6f7665727669732e636f6d"
    await client.set_setting("cloud_address", "6e74702e6c6f63616c")
    assert await client.get("cloud_address") == "6e74702e6c6f63616c"
    assert await client.get("cloud_port") == 20504
    await client.set_setting("cloud_port", 1234)
    assert await client.get("cloud_port") == "1234"
    await client.set_setting("cloud_port", 20504)
    await client.close()


def test_device_local_epoch():
    from novatek_em12x.const import device_local_epoch

    assert device_local_epoch(1000, 10800) == 11800
    assert device_local_epoch(0, 0) == 0
