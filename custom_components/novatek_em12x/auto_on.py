"""Safety auto-on: re-energise the load after it was switched off."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store

from .api import EMError
from .const import (
    CONF_AUTO_ON_DAYS,
    CONF_AUTO_ON_DELAY,
    CONF_AUTO_ON_ENABLED,
    CONF_AUTO_ON_EXTERNAL,
    CONF_AUTO_ON_HORIZON,
    CONF_AUTO_ON_RETRY,
    DEFAULT_AUTO_ON_DAYS,
    DEFAULT_AUTO_ON_DELAY,
    DEFAULT_AUTO_ON_HORIZON,
    DEFAULT_AUTO_ON_RETRY,
    DEVICE_DAY_SECONDS,
    DOMAIN,
    device_local_epoch,
    reserve_event_times,
)

if TYPE_CHECKING:
    from homeassistant.core import CALLBACK_TYPE, HomeAssistant

    from . import NovatekEMConfigEntry

_LOGGER = logging.getLogger(__name__)

EVENT_AUTO_ON = f"{DOMAIN}_auto_on"

REASON_MANUAL = "manual"
REASON_EXTERNAL = "external"


class AutoOnManager:
    """Turn the relay back on after a switch-off, persisted across restarts."""

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
        self._last_command = 0.0
        self.deadline: int | None = None
        self.end: int | None = None
        self.reason: str | None = None
        self._paused = False

    def _option(self, key: str, default: Any) -> Any:
        return self.entry.options.get(key, self.entry.data.get(key, default))

    @property
    def enabled(self) -> bool:
        """Safeguard for switch-offs initiated from Home Assistant."""
        return bool(self._option(CONF_AUTO_ON_ENABLED, False))

    @property
    def enabled_external(self) -> bool:
        """Safeguard for switch-offs made outside Home Assistant."""
        return bool(self._option(CONF_AUTO_ON_EXTERNAL, False))

    @property
    def delay_seconds(self) -> int:
        return int(self._option(CONF_AUTO_ON_DELAY, DEFAULT_AUTO_ON_DELAY)) * 60

    @property
    def reserve_days(self) -> int:
        return int(self._option(CONF_AUTO_ON_DAYS, DEFAULT_AUTO_ON_DAYS))

    @property
    def retry_seconds(self) -> int:
        return int(self._option(CONF_AUTO_ON_RETRY, DEFAULT_AUTO_ON_RETRY)) * 60

    @property
    def horizon_seconds(self) -> int:
        return int(self._option(CONF_AUTO_ON_HORIZON, DEFAULT_AUTO_ON_HORIZON)) * 3600

    def note_command(self) -> None:
        """Remember that the integration is controlling the relay itself."""
        self._last_command = time.monotonic()

    def command_recent(self, window: float = 20.0) -> bool:
        return time.monotonic() - self._last_command < window

    @property
    def paused(self) -> bool:
        """True when auto-on is suppressed (e.g. maintenance work)."""
        return self._paused

    async def async_set_paused(self, paused: bool) -> None:
        """Suppress or re-enable auto-on; cancels any armed safeguard."""
        if paused:
            await self._finish(None)
        self._paused = paused
        await self._save()
        self.coordinator.async_update_listeners()
        _LOGGER.info("Auto-on %s", "paused" if paused else "resumed")

    async def async_load(self) -> None:
        stored = await self._store.async_load()
        self._data = dict(stored or {})
        self.deadline = self._data.get("deadline")
        self.end = self._data.get("end")
        self.reason = self._data.get("reason")
        self._paused = bool(self._data.get("paused", False))

    async def _save(self) -> None:
        self._data.update(
            {
                "deadline": self.deadline,
                "end": self.end,
                "reason": self.reason,
                "paused": self._paused,
            }
        )
        await self._store.async_save(self._data)

    def _schedule_next(self) -> None:
        if self._unsub is not None:
            self._unsub()
            self._unsub = None
        if self.deadline is None:
            return
        remaining = self.deadline - int(time.time())
        self._unsub = async_call_later(
            self.hass, max(1, remaining), self._async_fire
        )

    async def _async_fire(self, _now: Any) -> None:
        self._unsub = None
        await self.async_attempt()

    async def _device_schedule_empty(self) -> bool | None:
        try:
            return not await self.client.schedule()
        except EMError as err:
            _LOGGER.warning("Could not read the device schedule: %s", err)
            return None

    async def _arm_device_chain(self, first_delay: int, days: int) -> None:
        try:
            gmt = int(await self.client.get("time_gmt"))
            empty = await self._device_schedule_empty()
            if empty is not True:
                if empty is False:
                    _LOGGER.warning(
                        "Device schedule is not empty, skipping the on-device backup"
                    )
                return
            first = device_local_epoch(int(time.time()), gmt) + first_delay
            for when in reserve_event_times(first, days):
                await self.client.schedule_add(when, 0, DEVICE_DAY_SECONDS)
            await self.client.schedule_run()
            self._data["device_schedule"] = True
            _LOGGER.debug(
                "On-device reserve armed: %s day(s) from local epoch %s", days, first
            )
        except EMError as err:
            _LOGGER.warning("Could not set the on-device reserve: %s", err)

    async def async_arm(self, reason: str = REASON_MANUAL) -> None:
        """Arm the safeguard after the relay was switched off."""
        if reason == REASON_MANUAL and not self.enabled:
            return
        if reason == REASON_EXTERNAL and not self.enabled_external:
            return
        if self._paused:
            _LOGGER.info("Auto-on paused, not arming (%s)", reason)
            return
        if self.deadline is not None:
            return
        if self._unsub is not None:
            self._unsub()
            self._unsub = None
        now = int(time.time())
        self.reason = reason
        if reason == REASON_EXTERNAL:
            self.deadline = now + self.retry_seconds
            self.end = now + self.horizon_seconds
            await self._arm_device_chain(self.retry_seconds, self.reserve_days)
        else:
            self.deadline = now + self.delay_seconds
            self.end = self.deadline
            await self._arm_device_chain(self.delay_seconds, self.reserve_days)
        await self._save()
        self._schedule_next()
        self.coordinator.async_update_listeners()
        _LOGGER.info(
            "Auto-on armed (%s), next attempt at %s", reason, self.deadline
        )

    async def async_cancel(self) -> None:
        """Cancel a pending auto-on without reporting success."""
        await self._finish(None)

    async def _finish(self, event_reason: str | None) -> None:
        if self._unsub is not None:
            self._unsub()
            self._unsub = None
        if self._data.get("device_schedule"):
            try:
                await self.client.schedule_clear()
            except EMError as err:
                _LOGGER.warning("Could not clear the on-device auto-on events: %s", err)
        deadline = self.deadline
        self._data = {"paused": self._paused}
        self.deadline = None
        self.end = None
        self.reason = None
        await self._store.async_save(self._data)
        if event_reason:
            self.hass.bus.async_fire(
                EVENT_AUTO_ON,
                {
                    "entry_id": self.entry.entry_id,
                    "reason": event_reason,
                    "deadline": deadline,
                },
            )
            _LOGGER.info("Auto-on finished (%s)", event_reason)
        self.coordinator.async_update_listeners()

    async def async_attempt(self) -> None:
        """Try to switch the relay on now."""
        if self.deadline is None:
            return
        self.note_command()
        try:
            await self.client.ctrl(True)
        except EMError as err:
            _LOGGER.warning("Auto-on attempt failed, will retry: %s", err)
        if self.reason == REASON_MANUAL:
            await self._finish("auto-on")
            await self.coordinator.async_request_refresh()
            return
        now = int(time.time())
        if self.end is not None and now + self.retry_seconds > self.end:
            await self._finish("exhausted")
            return
        self.deadline = now + self.retry_seconds
        await self._save()
        self._schedule_next()
        self.coordinator.async_update_listeners()

    async def async_restore(self) -> None:
        """Restore a pending auto-on after a Home Assistant restart."""
        await self.async_load()
        if self._paused and self.deadline is not None:
            await self.async_cancel()
            return
        if self.deadline is None:
            return
        if self._data.get("device_schedule"):
            empty = await self._device_schedule_empty()
            if empty is True:
                await self._arm_device_chain(
                    max(1, self.deadline - int(time.time())),
                    self.reserve_days,
                )
        if int(time.time()) >= self.deadline:
            await self.async_attempt()
        else:
            self._schedule_next()
        self.coordinator.async_update_listeners()

    async def async_poll_check(self, relay_on: bool) -> None:
        """Resolve overdue attempts and successful recoveries."""
        if self.deadline is None:
            return
        if relay_on:
            await self._finish("confirmed")
            return
        if int(time.time()) >= self.deadline:
            await self.async_attempt()

    async def async_check_journal(
        self,
        transitions: list[dict[str, Any]],
        relay_on: bool,
        protection_active: bool,
    ) -> None:
        """Arm for switch-offs that happened while polls were missing."""
        if (
            relay_on
            or protection_active
            or not self.enabled_external
            or self.deadline is not None
            or not transitions
        ):
            return
        last = transitions[-1]
        if last["relay"]:
            return
        age = int(time.time()) - int(last["timestamp"])
        if age <= self.horizon_seconds:
            _LOGGER.info("External switch-off detected in the journal (%ss ago)", age)
            await self.async_arm(REASON_EXTERNAL)

    async def async_shutdown(self) -> None:
        if self._unsub is not None:
            self._unsub()
            self._unsub = None
