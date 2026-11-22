"""Data update coordinator for Novatek Electro EM."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EMAuthError, EMError
from .const import (
    CONF_SYNC_TIME,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SETTINGS_EVERY,
    DOMAIN,
    MEASUREMENT_PARAMS,
    MIN_SCAN_INTERVAL,
    SETTING_PARAMS,
    TIME_SYNC_INTERVAL,
)

if TYPE_CHECKING:
    from . import NovatekEMConfigEntry

_LOGGER = logging.getLogger(__name__)


def get_scan_interval(entry: NovatekEMConfigEntry) -> int:
    value = entry.options.get(
        "scan_interval", entry.data.get("scan_interval", DEFAULT_SCAN_INTERVAL)
    )
    return max(MIN_SCAN_INTERVAL, int(value))


@dataclass
class EMData:
    """Polled device data."""

    measurements: dict[str, Any] = field(default_factory=dict)
    settings: dict[str, Any] = field(default_factory=dict)
    cloud: dict[str, Any] = field(default_factory=dict)


class NovatekEMCoordinator(DataUpdateCoordinator[EMData]):
    """Coordinator that polls measurements and, less often, settings."""

    def __init__(
        self, hass: HomeAssistant, entry: NovatekEMConfigEntry, client: Any
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=get_scan_interval(entry)),
        )
        self.entry = entry
        self.client = client
        self._poll_count = 0
        self._last_time_sync = 0.0

    @property
    def sync_time_enabled(self) -> bool:
        return self.entry.options.get(
            CONF_SYNC_TIME, self.entry.data.get(CONF_SYNC_TIME, True)
        )

    async def _maybe_sync_time(self) -> None:
        if not self.sync_time_enabled:
            return
        if time.monotonic() - self._last_time_sync < TIME_SYNC_INTERVAL:
            return
        self._last_time_sync = time.monotonic()
        try:
            await self.client.set_clock(int(time.time()))
            _LOGGER.debug("Device clock synchronized")
        except EMError as err:
            _LOGGER.warning("Clock sync failed: %s", err)

    async def refresh_settings(self) -> tuple[dict[str, Any], dict[str, Any]]:
        settings: dict[str, Any] = self.data.settings if self.data else {}
        cloud: dict[str, Any] = self.data.cloud if self.data else {}
        try:
            settings = await self.client.get_many(SETTING_PARAMS)
        except EMError as err:
            _LOGGER.warning("Failed to refresh settings: %s", err)
        try:
            cloud = await self.client.cloud_info()
        except EMError as err:
            _LOGGER.debug("cloud_info unavailable: %s", err)
        return settings, cloud

    async def _async_update_data(self) -> EMData:
        try:
            measurements = await self.client.get_many(MEASUREMENT_PARAMS)
        except EMAuthError as err:
            raise ConfigEntryAuthFailed(f"Authentication with device failed: {err}") from err
        except EMError as err:
            raise UpdateFailed(f"Error communicating with device: {err}") from err

        self._poll_count += 1
        settings: dict[str, Any] = self.data.settings if self.data else {}
        cloud: dict[str, Any] = self.data.cloud if self.data else {}
        if not settings or self._poll_count % DEFAULT_SETTINGS_EVERY == 0:
            settings, cloud = await self.refresh_settings()

        await self._maybe_sync_time()
        return EMData(measurements=measurements, settings=settings, cloud=cloud)
