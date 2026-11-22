# Changelog

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
