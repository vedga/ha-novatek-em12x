"""Catch-up of device journals after a reconnect or Home Assistant restart."""

from __future__ import annotations

import logging
from time import monotonic
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.storage import Store

from .api import EMError
from .const import CATCHUP_MIN_INTERVAL, DOMAIN, EVENT_NAME_MAX
from .journals import (
    fault_mask_changes,
    is_reboot,
    latest_timestamp,
    newer_than,
    parse_journal,
    parse_syslog,
    relay_transitions,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from . import NovatekEMConfigEntry

_LOGGER = logging.getLogger(__name__)

EVENT_SYSLOG = f"{DOMAIN}_syslog"
EVENT_REBOOT = f"{DOMAIN}_reboot"
EVENT_FAULT = f"{DOMAIN}_fault"


class JournalCatchup:
    """Read missed device journal records and publish them as bus events."""

    def __init__(
        self, hass: HomeAssistant, entry: NovatekEMConfigEntry
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.host = str(entry.data.get("host", ""))
        self._store: Store[dict[str, int]] = Store(
            hass, 1, f"{DOMAIN}.{entry.entry_id}.journals"
        )
        self._data: dict[str, int] = {}
        self._loaded = False
        self._last_run = 0.0
        self.last_event: dict[str, Any] | None = None
        self.missed_syslog = 0
        self.missed_journal = 0
        self.relay_transitions: list[dict[str, Any]] = []

    async def async_load(self) -> None:
        stored = await self._store.async_load()
        self._data = dict(stored or {})
        self._loaded = True

    def _fire(self, event: str, payload: dict[str, Any]) -> None:
        self.hass.bus.async_fire(event, {"entry_id": self.entry.entry_id, **payload})

    async def async_catch_up(self, client: Any, force: bool = False) -> None:
        if not force and monotonic() - self._last_run < CATCHUP_MIN_INTERVAL:
            return
        self._last_run = monotonic()
        if not self._loaded:
            await self.async_load()

        baseline = not self._data
        try:
            syslog = parse_syslog(await client.syslog())
        except EMError as err:
            _LOGGER.debug("syslog catch-up failed: %s", err)
            syslog = []
        if syslog:
            since = int(self._data.get("syslog_ts", 0))
            newest = latest_timestamp(syslog)
            if since and newest < since:
                _LOGGER.warning(
                    "Device syslog went backwards (%s < %s), resetting baseline",
                    newest,
                    since,
                )
                since = newest
                baseline = True
            new = [] if baseline else newer_than(syslog, since)
            for record in new[-EVENT_NAME_MAX:]:
                self._fire(
                    EVENT_SYSLOG,
                    {
                        "timestamp": record["timestamp"],
                        "message": record["message"],
                        "host": self.host,
                    },
                )
                if is_reboot(record):
                    self._fire(
                        EVENT_REBOOT,
                        {"timestamp": record["timestamp"], "host": self.host},
                    )
            if new:
                self.last_event = new[-1]
                self.missed_syslog = len(new)
            elif baseline:
                self.last_event = syslog[-1]
            self._data["syslog_ts"] = latest_timestamp(syslog, since)

        try:
            journal = parse_journal(await client.journal())
        except EMError as err:
            _LOGGER.debug("journal catch-up failed: %s", err)
            journal = []
        if journal:
            since_j = int(self._data.get("journal_ts", 0))
            newest_j = latest_timestamp(journal)
            if since_j and newest_j < since_j:
                _LOGGER.warning(
                    "Device data log went backwards (%s < %s), resetting baseline",
                    newest_j,
                    since_j,
                )
                since_j = newest_j
                baseline = True
            new_j = [] if baseline else newer_than(journal, since_j)
            stored_relay = self._data.get("relay_on")
            previous_relay = None if stored_relay is None else bool(stored_relay)
            self.relay_transitions = relay_transitions(
                new_j, None if baseline else previous_relay
            )
            self._data["relay_on"] = int(bool(journal[-1]["sys_flags"] >> 4 & 1))
            if baseline:
                self._data["faul_mask"] = journal[-1]["faul_flags"]
            else:
                previous = int(self._data.get("faul_mask", 0))
                for change in fault_mask_changes(new_j, previous):
                    self._fire(
                        EVENT_FAULT,
                        {
                            "timestamp": change["timestamp"],
                            "raised": change["raised"],
                            "mask": change["mask"],
                            "host": self.host,
                        },
                    )
                if new_j:
                    self._data["faul_mask"] = new_j[-1]["faul_flags"]
                self.missed_journal = len(new_j)
            self._data["journal_ts"] = latest_timestamp(journal, since_j)

        await self._store.async_save(self._data)
