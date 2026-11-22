"""Local Web API emulator for the EM-129 meter used by the tests."""

from __future__ import annotations

import hashlib

from aiohttp import web

SALT = "1ddc4760"
PASSWORD = "secret"
PREFIX = "EM-129"

STATE = {
    "volt_msr": 2287,
    "cur_msr": 512,
    "powa_msr": 1150,
    "pows_msr": 1190,
    "freq_msr": 4999,
    "tempr_msr": 246,
    "enrga_msr": 12345,
    "enrgs_msr": 12901,
    "enrga_d_msr": 100,
    "enrga_w_msr": 500,
    "enrga_m_msr": 2000,
    "sys_flag": 1544749712,
    "faul_flag": 0,
    "ar_time": 0,
    "time": "1795361544 0",
    "volt_leveloff_hi": 255,
    "volt_leveloff_lo": 190,
    "pow_enable": 1,
    "led_intens": 12,
    "cost_unit": 13,
    "cost_energy": 1000,
    "cloud_enable": 1,
    "cur_leveloff": 630,
    "wifi_wdt_enable": 1,
}

SERIALIZED_LOG = []


class FakeDevice:
    def __init__(self) -> None:
        self.sids: set[str] = set()
        self.expire_all_sids = False
        self.fail_next = False
        self.app = self._build_app()
        self.runner: web.AppRunner | None = None

    def _build_app(self) -> web.Application:
        app = web.Application()
        app.router.add_route("*", "/{tail:.*}", self.handle)
        return app

    async def start(self) -> str:
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await site.start()
        port = self.runner.addresses[0][1]
        return f"127.0.0.1:{port}"

    async def stop(self) -> None:
        if self.runner:
            await self.runner.cleanup()

    async def handle(self, request: web.Request) -> web.Response:
        SERIALIZED_LOG.append(request.path_qs)
        if self.fail_next:
            self.fail_next = False
            raise web.HTTPServiceUnavailable
        path = request.path_qs
        if path == "/api/login?device_info":
            return web.json_response({"device_id": 271, "user_info": "454d2d313239", "STATUS": "OK"})
        if path == "/api/login?salt":
            return web.json_response({"SALT": SALT, "STATUS": "OK"})
        if path.startswith("/api/login?login="):
            digest = path.split("=", 1)[1]
            expected = hashlib.sha1(f"{PREFIX}{PASSWORD}{SALT}".encode()).hexdigest()
            if digest == expected:
                sid = "6c73ca5142916293cd"
                self.sids.add(sid)
                return web.json_response({"SID": sid, "STATUS": "OK"})
            return web.json_response({"STATUS": "ERROR_LOGIN"})
        if path.startswith("/api/login?logout="):
            self.sids.discard(path.split("=", 1)[1])
            return web.json_response({"STATUS": "OK"})
        if not path.startswith("/"):
            return web.json_response({"STATUS": "ERROR"})
        parts = path[1:].split("/", 1)
        if len(parts) != 2:
            return web.json_response({"STATUS": "SINTAXIS_ERROR"})
        sid, command = parts
        if self.expire_all_sids:
            self.sids.clear()
            self.expire_all_sids = False
        if sid not in self.sids:
            raise web.HTTPFound(location="/")
        if command.startswith("api/all/get?"):
            params = command.split("?", 1)[1].split("&")
            if all(p in STATE for p in params):
                payload = {p: STATE[p] for p in params}
                payload["STATUS"] = "OK"
                return web.json_response(payload)
            return web.json_response({"STATUS": "SINTAXIS_ERROR"})
        if command.startswith("api/settings/set?"):
            pairs = command.partition("?")[2].split("&")
            parsed = []
            for pair in pairs:
                param, _, value = pair.partition("=")
                parsed.append((param, value))
            if all(param in STATE for param, _ in parsed):
                for param, value in parsed:
                    STATE[param] = value
                return web.json_response({"STATUS": "OK"})
            return web.json_response({"STATUS": "SINTAXIS_ERROR"})
        if command.startswith("api/firmw/fwinfo"):
            return web.json_response(
                {"NEW_VERSION": "ERROR_NOT_FOUND", "CUR_VERSION": "1.271.3.34", "STATUS": "OK"}
            )
        if command == "api/utils/cloud_info":
            return web.json_response(
                {
                    "STAT": 4,
                    "SECR": 1,
                    "AUTH": 1,
                    "LCMD": "0004",
                    "LERR": "0000",
                    "SERV": "my.overvis.com",
                    "PORT": 20504,
                    "STATUS": "OK",
                }
            )
        if command in ("api/utils/ctrl?on", "api/utils/ctrl?off", "api/utils/reboot", "api/utils/enrgrst"):
            return web.json_response({"STATUS": "OK"})
        if command.startswith("api/clock/set?sec="):
            STATE["time"] = f"{command.split('=')[1]} 0"
            return web.json_response({"STATUS": "OK"})
        if command == "api/clock/sync":
            return web.json_response({"STATUS": "OK"})
        return web.json_response({"STATUS": "SINTAXIS_ERROR"})
