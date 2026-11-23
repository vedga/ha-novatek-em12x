# Changelog

## 1.8.0

- external (billing) meter reading: map the device energy counter to the
  certified meter value with one rebase field (initial setup and periodic
  correction are the same operation); automatic rebase on device counter
  reset, persisted across restarts, novatek_em12x_billing bus event
- fix: reclose countdown sensor rescales ar_time from device milliseconds to
  seconds (documentation wrongly says seconds)
- docs: frequency protection test results (high/low threshold bits, continuous
  out-of-range behaviour, fault clearing without reboot)
- localization: Polish and Ukrainian translations (device-supported languages);
  now en, ru, pl, uk with full key parity

## 1.7.0

- on-device reserve is now configurable in days (1–7): a chain of daily
  schedule events with a 60 s overlap keeps the relay continuously on;
  events survive device reboots
- verified on hardware: the RTC keeps time for at least 15 minutes without
  power and without NTP, and the relay state is restored after power-on
  (ON stays ON, OFF stays OFF); documented with the remaining RTC-duration
  uncertainty

## 1.6.0

- auto-on retry interval defaults to 10 minutes (HA itself needs ~5 min to boot
  after a power loss)
- new "Pause auto-on" switch: suppresses both safeguards, immediately cancels
  timers and removes the on-device backup event; persisted across restarts —
  use it before any work on the power network

## 1.5.0

- auto-on for switch-offs made outside Home Assistant (front-panel 3 s hold):
  detected by relay state transitions and by extra data-log samples, then
  retried every N minutes within a configurable window, with an on-device
  hold event (persisted across reboots) as the real recovery path when the
  network gear is powered through the relay; toggleable, restart-safe
- docs: panel button behaviour, new options and limitations

## 1.4.0

- journal catch-up after network loss or HA restart: syslog/data-log are read
  and published as bus events (novatek_em12x_syslog / _reboot / _fault),
  last seen timestamps persisted in a Store; new diagnostic sensors
- safety auto-on after a manual switch-off: HA timer plus on-device schedule
  backup, persisted across restarts, with cancel button and options
  (enable, delay in minutes, backup duration in hours)

## 1.3.1

- add a local brand icon (`brand/icon.png`) and make the HACS validation run
  without ignores (required for the default HACS list)
- CI: HACS action + hassfest

## 1.3.0

- fix: cloud diagnostic sensors no longer drop to unknown between polls
- reauth flow for a changed device password (verified by MAC)
- config flow reports an invalid password separately from connection errors
- entities refresh from the device after a failed write instead of keeping
  the optimistic value until the next settings poll
- select entities ignore values outside the option list
- NTP/cloud sync sensors are proper enums with translated states
- tariff/cost sensors: display precision; diagnostics download support
- device card links to the meter web interface
- unsupported parameters are remembered (warn once) and reset on login
- small cleanups
- docs: supported models and auth-prefix caveat, Energy dashboard walkthrough,
  debug logging recipes, cloud field availability, corrected entity counts,
  CHANGELOG

## 1.2.2

- cloud server address (`cloud_address`, hex text) and port (`cloud_port`) entities,
  unavailable while remote cloud access is disabled

## 1.2.1

- switch for the cloud remote-access setting (`cloud_enable`)

## 1.2.0

- tariff sensor (`<currency>/kWh`) usable as the Energy dashboard price entity
- cost sensors: total, daily, weekly, monthly (calculated as kWh × tariff,
  same formula as the device web UI)

## 1.1.1

- fix: recover the session after device reboot (HTTP 302 / non-JSON responses
  previously left all entities unavailable until a Home Assistant restart)

## 1.1.0

- reconfigure flow: change host/password in place, verified by MAC, keeping
  unique_id, entities and history
- debug logging for every write action and API command

## 1.0.0

- initial integration: 8 platforms, batched polling, config and options flows
- login with salted SHA1, automatic re-login, firmware quirks handled
  (hex string settings, UTC clock/set, no range validation)
- hardware-validated against a real EM-129; unit tests on a device emulator
