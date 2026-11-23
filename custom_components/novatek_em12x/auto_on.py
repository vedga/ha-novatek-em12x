"""Safety auto-on: re-energise the load after a manual switch-off."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store

from .api import EMError
from .const import (
    CONF_AUTO_ON_DELAY,
    CONF_AUTO_ON_DURATION,
    CONF_AUTO_ON_ENABLED,
    DEFAULT_AUTO_ON_DELAY,
    DEFAULT_AUTO_ON_DURATION,
    DOMAIN,
    device_local_epoch,
)

if TYPE_CHECKING:
    from homeassistant.core import CALLBACK_TYPE, HomeAssistant

    from . import NovatekEMConfigEntry

_LOGGER = logging.getLogger(__name__)

EVENT_AUTO_ON = f"{DOMAIN}_auto_on"


class AutoOnManager:
    """Turn the relay back on after a delay, persisted across restarts."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: NovatekEMConfigEntry,
        client: Any,
        coordinator: Any,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.client = client
        self.coordinator = coordinator
        self._store: Store[dict[str, Any]] = Store(
            hass, 1, f"{DOMAIN}.{entry.entry_id}.auto_on"
        )
        self._data: dict[str, Any] = {}
        self._unsub: CALLBACK_TYPE | None = None
        self.deadline: int | None = None

    def _option(self, key: str, default: Any) -> Any:
        return self.entry.options.get(key, self.entry.data.get(key, default))

    @property
    def enabled(self) -> bool:
        return bool(self._option(CONF_AUTO_ON_ENABLED, False))

    @property
    def delay_seconds(self) -> int:
        return int(self._option(CONF_AUTO_ON_DELAY, DEFAULT_AUTO_ON_DELAY)) * 60

    @property
    def duration_seconds(self) -> int:
        return int(self._option(CONF_AUTO_ON_DURATION, DEFAULT_AUTO_ON_DURATION)) * 3600

    async def async_load(self) -> None:
        stored = await self._store.async_load()
        self._data = dict(stored or {})
        self.deadline = self._data.get("deadline")

    def _schedule(self, seconds: float) -> None:
        if self._unsub is not None:
            self._unsub()
        self._unsub = async_call_later(self.hass, max(1, seconds), self._async_fire)

    async def _async_fire(self, _now: Any) -> None:
        await self.async_trigger("timer")

    async def async_arm(self) -> None:
        """Arm the safeguard after the relay was switched off manually."""
        if not self.enabled:
            return
        if self._unsub is not None:
            self._unsub()
            self._unsub = None
        deadline = int(time.time()) + self.delay_seconds
        self.deadline = deadline
        self._data = {"deadline": deadline, "device_schedule": False}
        try:
            gmt = int(await self.client.get("time_gmt"))
            existing = await self.client.schedule()
            if existing:
                _LOGGER.warning(
                    "Device schedule is not empty, skipping the on-device backup"
                )
            else:
                when = device_local_epoch(int(time.time()), gmt) + self.delay_seconds
                await self.client.schedule_add(when, 0, self.duration_seconds)
                await self.client.schedule_run()
                self._data["device_schedule"] = True
                _LOGGER.debug("On-device auto-on event set at local epoch %s", when)
        except EMError as err:
            _LOGGER.warning("Could not set the on-device auto-on backup: %s", err)
        await self._store.async_save(self._data)
        self._schedule(self.delay_seconds)
        self.coordinator.async_update_listeners()
        _LOGGER.info("Auto-on armed for %s seconds", self.delay_seconds)

    async def async_cancel(self) -> None:
        """Cancel a pending auto-on (manual on, or user request)."""
        if self._unsub is not None:
            self._unsub()
            self._unsub = None
        if self._data.get("device_schedule"):
            try:
                await self.client.schedule_clear()
            except EMError as err:
                _LOGGER.warning("Could not clear the on-device auto-on event: %s", err)
        if self.deadline is not None:
            _LOGGER.info("Auto-on cancelled")
        self._data = {}
        self.deadline = None
        await self._store.async_save(self._data)
        self.coordinator.async_update_listeners()

    async def async_trigger(self, reason: str) -> None:
        """Switch the relay on and clear the safeguard."""
        if self.deadline is None:
            return
        deadline = self.deadline
        try:
            await self.client.ctrl(True)
        except EMError as err:
            _LOGGER.warning("Auto-on failed, will retry on next poll: %s", err)
            return
        device_schedule = bool(self._data.get("device_schedule"))
        if self._unsub is not None:
            self._unsub()
            self._unsub = None
        if device_schedule:
            try:
                await self.client.schedule_clear()
            except EMError as err:
                _LOGGER.warning("Could not clear the on-device auto-on event: %s", err)
        self._data = {}
        self.deadline = None
        await self._store.async_save(self._data)
        self.hass.bus.async_fire(
            EVENT_AUTO_ON,
            {
                "entry_id": self.entry.entry_id,
                "reason": reason,
                "deadline": deadline,
            },
        )
        _LOGGER.info("Auto-on relay turned on (%s)", reason)
        await self.coordinator.async_request_refresh()

    async def async_restore(self) -> None:
        """Restore a pending auto-on after a Home Assistant restart."""
        await self.async_load()
        if self.deadline is None:
            return
        remaining = self.deadline - int(time.time())
        if remaining <= 0:
            _LOGGER.info("Auto-on deadline passed while offline, restoring now")
            await self.async_trigger("restore-overdue")
            return
        self._schedule(remaining)
        if self._data.get("device_schedule"):
            try:
                if not await self.client.schedule():
                    gmt = int(await self.client.get("time_gmt"))
                    when = device_local_epoch(int(time.time()), gmt) + remaining
                    await self.client.schedule_add(
                        when, 0, self.duration_seconds
                    )
                    await self.client.schedule_run()
                    _LOGGER.info("Re-armed the on-device auto-on event")
            except EMError as err:
                _LOGGER.warning("Could not re-arm the on-device event: %s", err)
        self.coordinator.async_update_listeners()

    async def async_poll_check(self, relay_on: bool) -> None:
        """Resolve overdue deadlines and external switch-on events."""
        if self.deadline is None:
            return
        if relay_on:
            await self.async_cancel()
            return
        if int(time.time()) >= self.deadline:
            await self.async_trigger("poll-overdue")

    async def async_shutdown(self) -> None:
        if self._unsub is not None:
            self._unsub()
            self._unsub = None
