"""Persisted external meter baseline, reading and calibration coefficients."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.storage import Store

from .billing import compute_reading, fit_coefficients, should_rebase
from .const import (
    BILLING_FIT_MAX_HISTORY,
    BILLING_FIT_MIN_INTERVALS,
    CONF_BILLING_AUTO_TUNE,
    DEFAULT_BILLING_AUTO_TUNE,
    DOMAIN,
    MAX_BILLING_CALIBRATION,
    MAX_BILLING_SELF_POWER,
    MIN_BILLING_CALIBRATION,
    MIN_BILLING_SELF_POWER,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from . import NovatekEMConfigEntry

_LOGGER = logging.getLogger(__name__)

EVENT_BILLING = f"{DOMAIN}_billing"


class BillingManager:
    """Map the device energy counter to an external billing meter reading."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: NovatekEMConfigEntry,
        coordinator: Any,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.coordinator = coordinator
        self._store: Store[dict[str, Any]] = Store(
            hass, 1, f"{DOMAIN}.{entry.entry_id}.billing"
        )
        self._loaded = False
        self.base_kwh: float | None = None
        self.device_wh_at_base: int | None = None
        self.last_device_wh: int | None = None
        self.reading: float | None = None
        self.updated_at: int | None = None
        self.self_power_w: float = 0.0
        self.calibration_pct: float = 0.0
        self.history: list[dict[str, Any]] = []

    async def async_load(self) -> None:
        data = await self._store.async_load() or {}
        self.base_kwh = data.get("base_kwh")
        self.device_wh_at_base = data.get("device_wh_at_base")
        self.last_device_wh = data.get("last_device_wh")
        self.reading = data.get("reading")
        self.updated_at = data.get("updated_at")
        self.self_power_w = float(data.get("self_power_w") or 0.0)
        self.calibration_pct = float(data.get("calibration_pct") or 0.0)
        self.history = list(data.get("history") or [])
        self._loaded = True

    def _data(self) -> dict[str, Any]:
        return {
            "base_kwh": self.base_kwh,
            "device_wh_at_base": self.device_wh_at_base,
            "last_device_wh": self.last_device_wh,
            "reading": self.reading,
            "updated_at": self.updated_at,
            "self_power_w": self.self_power_w,
            "calibration_pct": self.calibration_pct,
            "history": self.history[-BILLING_FIT_MAX_HISTORY:],
        }

    async def _save(self, delay: float = 0) -> None:
        data = self._data()
        if delay:
            self._store.async_delay_save(lambda: data, delay)
        else:
            await self._store.async_save(data)

    def _now(self) -> int:
        return int(time.time())

    def _reading_now(self, device_wh: int, now_ts: int) -> float:
        assert self.base_kwh is not None and self.device_wh_at_base is not None
        return compute_reading(
            self.base_kwh,
            self.device_wh_at_base,
            device_wh,
            self.self_power_w,
            self.calibration_pct,
            self.updated_at,
            now_ts,
        )

    def _history_point(self, now_ts: int, device_wh: int, kwh: float) -> None:
        self.history.append(
            {"ts": now_ts, "device_wh": int(device_wh), "kwh": round(float(kwh), 3)}
        )
        self.history = self.history[-BILLING_FIT_MAX_HISTORY:]

    @property
    def auto_tune_enabled(self) -> bool:
        return bool(
            self.entry.options.get(
                CONF_BILLING_AUTO_TUNE,
                self.entry.data.get(CONF_BILLING_AUTO_TUNE, DEFAULT_BILLING_AUTO_TUNE),
            )
        )

    def _fire(self, reason: str, value: float | None, **extra: Any) -> None:
        self.hass.bus.async_fire(
            EVENT_BILLING,
            {
                "entry_id": self.entry.entry_id,
                "reason": reason,
                "value": value,
                "base_kwh": self.base_kwh,
                "device_wh_at_base": self.device_wh_at_base,
                "self_power_w": self.self_power_w,
                "calibration_pct": self.calibration_pct,
                **extra,
            },
        )

    async def async_update(self, device_wh: int) -> None:
        """Update the reading; rebase automatically if the counter was reset."""
        if not self._loaded:
            await self.async_load()
        device_wh = int(device_wh)
        now_ts = self._now()
        if self.base_kwh is None or self.device_wh_at_base is None:
            self.base_kwh = round(device_wh / 1000, 3)
            self.device_wh_at_base = device_wh
            self.last_device_wh = device_wh
            self.reading = self.base_kwh
            self.updated_at = now_ts
            self.history.clear()
            self._history_point(now_ts, device_wh, self.base_kwh)
            await self._save()
            return
        if should_rebase(self.last_device_wh, device_wh):
            previous = self.reading if self.reading is not None else self.base_kwh
            _LOGGER.info(
                "Device energy counter reset (%s -> %s Wh), rebasing external meter",
                self.last_device_wh,
                device_wh,
            )
            self.base_kwh = round(float(previous), 3)
            self.device_wh_at_base = device_wh
            self.updated_at = now_ts
            self.history.clear()
            self._history_point(now_ts, device_wh, self.base_kwh)
            self._fire("reset", self.base_kwh)
        self.last_device_wh = device_wh
        self.reading = self._reading_now(device_wh, now_ts)
        await self._save(delay=60)

    async def async_set_reading(self, value: float, device_wh: int) -> None:
        """Rebase the external reading to the current device counter."""
        if not self._loaded:
            await self.async_load()
        device_wh = int(device_wh)
        now_ts = self._now()
        residual: float | None = None
        fit: dict[str, float | None] | None = None
        if self.base_kwh is not None and self.device_wh_at_base is not None:
            residual = round(float(value) - self._reading_now(device_wh, now_ts), 3)
        self._history_point(now_ts, device_wh, value)
        if residual is not None:
            fit = fit_coefficients(
                self.history, min_intervals=BILLING_FIT_MIN_INTERVALS
            )
            if fit is not None and self.auto_tune_enabled:
                self._apply_fit(fit)

        self.base_kwh = round(float(value), 3)
        self.device_wh_at_base = device_wh
        self.last_device_wh = device_wh
        self.reading = self.base_kwh
        self.updated_at = now_ts
        await self._save()
        extra: dict[str, Any] = {
            "residual_kwh": residual,
            "auto_tuned": bool(fit is not None and self.auto_tune_enabled),
            "history_points": len(self.history),
        }
        if fit is not None:
            extra["suggested_self_power_w"] = fit.get("self_power_w")
            extra["suggested_calibration_pct"] = (
                None
                if fit.get("scale") is None
                else round((float(fit["scale"]) - 1) * 100, 2)
            )
        self._fire("manual", self.base_kwh, **extra)
        self.coordinator.async_update_listeners()
        _LOGGER.info(
            "External meter rebased to %s kWh (residual %s kWh)",
            self.base_kwh,
            residual,
        )

    def _apply_fit(self, fit: dict[str, float | None]) -> None:
        self_power = fit.get("self_power_w")
        if self_power is not None:
            self.self_power_w = round(
                min(max(float(self_power), MIN_BILLING_SELF_POWER), MAX_BILLING_SELF_POWER),
                2,
            )
        scale = fit.get("scale")
        if scale is not None:
            calibration = (float(scale) - 1) * 100
            self.calibration_pct = round(
                min(
                    max(calibration, MIN_BILLING_CALIBRATION),
                    MAX_BILLING_CALIBRATION,
                ),
                2,
            )
        _LOGGER.info(
            "Billing coefficients updated: self_power=%s W, calibration=%s %%",
            self.self_power_w,
            self.calibration_pct,
        )

    async def async_set_self_power(self, value: float) -> None:
        """Set the device self-consumption (W) manually."""
        if not self._loaded:
            await self.async_load()
        self.self_power_w = round(
            min(max(float(value), MIN_BILLING_SELF_POWER), MAX_BILLING_SELF_POWER), 2
        )
        self._reset_history()
        await self._save()
        self._fire("coefficients", self.self_power_w, field="self_power_w")
        self.coordinator.async_update_listeners()

    async def async_set_calibration(self, value: float) -> None:
        """Set the counter calibration factor (%) manually."""
        if not self._loaded:
            await self.async_load()
        self.calibration_pct = round(
            min(max(float(value), MIN_BILLING_CALIBRATION), MAX_BILLING_CALIBRATION), 2
        )
        self._reset_history()
        await self._save()
        self._fire("coefficients", self.calibration_pct, field="calibration_pct")
        self.coordinator.async_update_listeners()

    def _reset_history(self) -> None:
        """Restart regression accumulation from the current point."""
        now_ts = self._now()
        device_wh = self.last_device_wh if self.last_device_wh is not None else 0
        kwh = self.reading if self.reading is not None else (self.base_kwh or 0.0)
        self.history.clear()
        self._history_point(now_ts, device_wh, kwh)
