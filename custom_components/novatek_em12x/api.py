"""Async client for the Novatek Electro EM-125/126T/129 Web API."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import Any
from urllib.parse import quote

import aiohttp

from .const import LOGIN_PREFIX

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)
AUTH_STATUSES = {"ERROR_LOGIN", "ERROR_SESSION", "ERROR_SID"}
QUIET_STATUSES = {"EOSL", "EOL", "EOE"}


class EMError(Exception):
    """Base error for the EM API client."""


class EMConnectionError(EMError):
    """The device is unreachable or returned invalid data."""


class EMAuthError(EMError):
    """Authentication with the device failed."""


class EMApiStatusError(EMError):
    """The device rejected a request."""

    def __init__(self, status: str) -> None:
        super().__init__(status)
        self.status = status


class EMSessionExpired(EMError):
    """The device answered with a non-JSON redirect, meaning the SID is invalid."""


def decode_setting_str(raw: str) -> str:
    """Decode a hex-encoded string setting (firmware uses hex, not base64)."""
    value = raw.strip()
    if not value:
        return ""
    try:
        decoded = bytes.fromhex(value).decode("ascii", "strict")
    except ValueError:
        return value
    return decoded if decoded.isprintable() else value


def encode_setting_str(value: str) -> str:
    """Hex-encode a string setting for the device."""
    return value.encode("ascii", "replace").hex()


class EMApiClient:
    """Thin async wrapper around the EM Web API."""

    def __init__(self, host: str, password: str, session: aiohttp.ClientSession) -> None:
        self._host = host
        self._password = password
        self._session = session
        self._sid: str | None = None
        self._lock = asyncio.Lock()
        self._unsupported: set[str] = set()

    @property
    def base_url(self) -> str:
        return f"http://{self._host}"


    async def close(self) -> None:
        async with self._lock:
            if self._sid:
                sid, self._sid = self._sid, None
                try:
                    await self._request(f"/api/login?logout={sid}")
                except EMError:
                    _LOGGER.debug("Logout failed for %s", self._host)

    async def device_info(self) -> dict[str, Any]:
        data = await self._request("/api/login?device_info")
        return {"device_id": data.get("device_id"), "user_info": data.get("user_info", "")}

    async def login(self) -> str:
        salt_data = await self._request("/api/login?salt")
        salt = salt_data.get("SALT")
        if not salt:
            raise EMAuthError("Device did not return a salt")
        digest = hashlib.sha1(
            f"{LOGIN_PREFIX}{self._password}{salt}".encode()
        ).hexdigest()
        data = await self._request(f"/api/login?login={digest}")
        sid = data.get("SID")
        if not sid:
            raise EMAuthError("Device did not return a session id")
        self._sid = sid
        self._unsupported.clear()
        _LOGGER.debug("Logged in to %s (sid=%s)", self._host, sid)
        return sid

    async def _ensure_sid(self) -> str:
        if self._sid is None:
            await self.login()
        assert self._sid is not None
        return self._sid

    async def _request(self, path: str) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            async with self._session.get(
                url, timeout=REQUEST_TIMEOUT, allow_redirects=False
            ) as resp:
                body = await resp.text()
                status_code = resp.status
        except (TimeoutError, aiohttp.ClientError) as err:
            raise EMConnectionError(f"{self._host}: {err}") from err
        if status_code in (301, 302, 303, 307, 308):
            raise EMSessionExpired(f"{self._host}: HTTP {status_code} redirect")
        if status_code != 200:
            raise EMConnectionError(f"{self._host} returned HTTP {status_code}")
        try:
            data: dict[str, Any] = json.loads(body)
        except ValueError as err:
            raise EMSessionExpired(f"{self._host}: non-JSON response") from err
        status = data.get("STATUS")
        if status not in (None, "OK", *QUIET_STATUSES):
            _LOGGER.debug("Device %s status %s for %s", self._host, status, path)
        return data

    async def _sid_request(self, path: str, relogin: bool = True) -> dict[str, Any]:
        async with self._lock:
            sid = await self._ensure_sid()
            try:
                data = await self._request(f"/{sid}{path}")
            except EMSessionExpired:
                if not relogin:
                    raise
                _LOGGER.debug("Session expired on %s, re-logging in", self._host)
                self._sid = None
                sid = await self._ensure_sid()
                data = await self._request(f"/{sid}{path}")
            if data.get("STATUS") in AUTH_STATUSES and relogin:
                _LOGGER.debug("Session expired on %s, re-logging in", self._host)
                self._sid = None
                sid = await self._ensure_sid()
                data = await self._request(f"/{sid}{path}")
            return data

    async def get(self, param: str) -> Any:
        data = await self._sid_request(f"/api/all/get?{param}")
        status = data.get("STATUS")
        if status == "OK" and param in data:
            return data[param]
        if status in AUTH_STATUSES:
            raise EMAuthError(status)
        raise EMApiStatusError(status or "NO_RESPONSE")

    async def get_many(self, params: list[str] | tuple[str, ...]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        supported = [p for p in params if p not in self._unsupported]
        if not supported:
            return result
        if len(supported) != len(params):
            _LOGGER.debug(
                "Skipping unsupported parameters: %s",
                sorted(set(params) - set(supported)),
            )
        params = supported
        path = "/api/all/get?" + "&".join(params)
        data = await self._sid_request(path)
        if data.get("STATUS") == "OK" and all(param in data for param in params):
            return {param: data[param] for param in params}
        _LOGGER.debug(
            "Batched get failed (%s), falling back to per-parameter requests",
            data.get("STATUS"),
        )
        for param in params:
            try:
                result[param] = await self.get(param)
            except EMApiStatusError as err:
                if param not in self._unsupported:
                    self._unsupported.add(param)
                    _LOGGER.warning(
                        "Parameter %s unavailable and will be skipped: %s",
                        param,
                        err.status,
                    )
        return result

    async def set_setting(self, param: str, value: Any) -> None:
        _LOGGER.debug("Set %s=%s", param, value)
        data = await self._sid_request(
            f"/api/settings/set?{param}={quote(str(value), safe='')}"
        )
        status = data.get("STATUS")
        if status != "OK":
            raise EMApiStatusError(status or "NO_RESPONSE")

    async def ctrl(self, on: bool) -> None:
        _LOGGER.debug("Relay command: %s", "on" if on else "off")
        data = await self._sid_request(f"/api/utils/ctrl?{'on' if on else 'off'}")
        status = data.get("STATUS")
        if status != "OK":
            raise EMApiStatusError(status or "NO_RESPONSE")

    async def fwinfo(self) -> dict[str, Any]:
        data = await self._sid_request("/api/firmw/fwinfo")
        status = data.get("STATUS")
        if status != "OK":
            raise EMApiStatusError(status or "NO_RESPONSE")
        return data

    async def _paginate(self, path: str, key: str) -> list[Any]:
        rows: list[Any] = []
        offset = 0
        for _ in range(50):
            data = await self._sid_request(f"{path}?offset={offset}")
            page = data.get(key, [])
            rows.extend(page)
            if data.get("STATUS") != "OK" or not page:
                break
            next_offset = data.get("OFFSET", offset)
            if next_offset == offset:
                break
            offset = next_offset
        return rows

    async def syslog(self) -> list[list[Any]]:
        return await self._paginate("/api/syslog/get", "SYSLOGS")

    async def journal(self) -> list[list[Any]]:
        return await self._paginate("/api/loger/get", "LOGS")

    async def schedule(self) -> list[list[Any]]:
        return await self._paginate("/api/event/get", "EVENTS")

    async def schedule_clear(self) -> None:
        data = await self._sid_request("/api/event/delall")
        status = data.get("STATUS")
        if status != "OK":
            raise EMApiStatusError(status or "NO_RESPONSE")

    async def schedule_add(self, when: int, repeat: int, live: int) -> None:
        data = await self._sid_request(
            f"/api/event/set?time={int(when)}&repeat={int(repeat)}"
            f"&live={int(live)}&flags=0&value=1"
        )
        status = data.get("STATUS")
        if status != "OK":
            raise EMApiStatusError(status or "NO_RESPONSE")

    async def schedule_run(self) -> None:
        data = await self._sid_request("/api/event/run")
        status = data.get("STATUS")
        if status != "OK":
            raise EMApiStatusError(status or "NO_RESPONSE")

    async def cloud_info(self) -> dict[str, Any]:
        data = await self._sid_request("/api/utils/cloud_info")
        status = data.get("STATUS")
        if status != "OK":
            raise EMApiStatusError(status or "NO_RESPONSE")
        return data

    async def reboot(self) -> None:
        _LOGGER.debug("Reboot command")
        await self._sid_request("/api/utils/reboot")

    async def energy_reset(self) -> None:
        _LOGGER.debug("Energy reset command")
        data = await self._sid_request("/api/utils/enrgrst")
        status = data.get("STATUS")
        if status != "OK":
            raise EMApiStatusError(status or "NO_RESPONSE")

    async def set_clock(self, timestamp: int) -> None:
        _LOGGER.debug("Clock set to %s", timestamp)
        data = await self._sid_request(f"/api/clock/set?sec={int(timestamp)}")
        status = data.get("STATUS")
        if status != "OK":
            raise EMApiStatusError(status or "NO_RESPONSE")

    async def sync_clock(self) -> None:
        _LOGGER.debug("Clock NTP sync command")
        data = await self._sid_request("/api/clock/sync")
        status = data.get("STATUS")
        if status != "OK":
            raise EMApiStatusError(status or "NO_RESPONSE")
