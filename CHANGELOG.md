# Changelog

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
