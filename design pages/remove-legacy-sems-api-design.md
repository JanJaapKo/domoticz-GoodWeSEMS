# Design: Remove the Legacy SEMS API and Feature Flag

## Goal

Make the current SEMS+ API the plugin's only supported account and telemetry path. The legacy SEMS API is no longer accessible, so the `Mode4` feature flag, legacy client routes, and fallbacks to legacy endpoints should be removed rather than retained as a nonfunctional compatibility option.

## Verified current behavior

- `plugin.py` declares `Mode4` as "use SEMS + API". `onStart()` selects `GoodWeSEMSPlus` when enabled and `GoodWe` otherwise. `onHeartbeat()` has separate SEMS+ and legacy scheduling paths.
- `GoodWeSEMSPlus` inherits from `GoodWe`. The base class still implements legacy login, station-list, monitor-data, and inverter-control requests.
- SEMS+ login first calls `NEW_LOGIN_URL`, then falls back to `OLD_LOGIN_URL` when the new login fails.
- SEMS+ station discovery, station telemetry, and per-inverter telemetry use the current SEMS+ Web endpoints. `GoodWeSEMSPlus.setInverterStatus()` is an exception: it still routes through the legacy `/PowerStation/SaveRemoteControlInverter` endpoint.
- `plugin.py` has an old `onConnect()` callback that calls `startDeviceUpdate(Connection)`, but no corresponding `startDeviceUpdate` method exists. The active polling path is `startDeviceUpdateV2()`.
- `README.md` asks users upgrading to v5 to enable the SEMS+ flag. `CONTRIBUTING.md` still describes retaining and testing the legacy route.

## Proposed design

### 1. Make SEMS+ the only plugin client

- Remove the `Mode4` parameter from the plugin XML.
- Always initialize the SEMS+ account in `onStart()` and keep one heartbeat scheduling path using the configured refresh interval.
- Remove the obsolete connection-driven `onConnect()` path and its wrapper if no remaining plugin workflow uses it. Remove `httpConn`/disconnect handling only if verification confirms they are exclusively tied to that dead path.
- Existing Domoticz configurations may still contain a persisted `Mode4` value. Ignore it; users should not need to edit or recreate hardware after upgrade.

### 2. Remove legacy request implementations

Remove the legacy concrete client behavior from `GoodWe`, including its legacy `tokenRequest()`, `stationListRequest()`, legacy `powerStationListRequest()`, monitor `stationDataRequest()`, and legacy `setInverterStatus()` methods. Preserve only genuinely shared model/account behavior needed by SEMS+ (for example, the account initialization and station retry/normalization contract), moving that behavior to a clearly named internal base if necessary. Keep `GoodWeSEMSPlus` as the sole concrete API client unless a class rename is justified by the implementation.

Remove the SEMS+ `_get_legacy_login_token()` fallback and fail login cleanly when the SEMS+ login fails. Remove legacy route rewriting and constants that become unused, including `_LegacyApiFallback`, `OLD_LOGIN_URL`, `_DefaultHeaders`, and the retired PowerStation route constants. Keep the SEMS+ gateway fallback used when the new login response omits an API URL; it is not the legacy API fallback.

Remove `GoodWeSEMSPlus.setInverterStatus()` while it targets the legacy PowerStation control endpoint. No verified SEMS+ replacement is present in this code. If remote control is a required feature, confirm its supported SEMS+ contract separately before implementing a replacement; do not silently route commands to the retired endpoint.

### 3. Preserve the current SEMS+ contract

Retain the SEMS+ login endpoint, regional gateway handling, station-page discovery, all-status device discovery, inverter telemetry and counters, signature generation, and the normalized `{"info": ..., "inverter": [...]}` data passed to `createStationV2()` and `updateDevices()`.

Simplify the shared station-data retry path only as needed to remove legacy response-envelope handling. Keep retries for transport errors and token refresh behavior, but test against normalized SEMS+ responses rather than legacy `{code, data}` payloads.

## Methods and paths to remove or review

- `GoodWe.tokenRequest()` and its `/v2/Common/CrossLogin` request.
- `GoodWe.stationListRequest()` and `/HistoryData/QueryPowerStationByHistory`.
- `GoodWe.powerStationListRequest()` and `/v3/PowerStation/GetPowerStationList`.
- `GoodWe.stationDataRequest()` and `/PowerStation/GetMonitorDetailByPowerstationId`.
- Both implementations of `setInverterStatus()` that call `/PowerStation/SaveRemoteControlInverter`; no SEMS+ replacement has been verified.
- `GoodWeSEMSPlus._get_legacy_login_token()` and its `OLD_LOGIN_URL` request.
- Legacy API base-rewrite helpers and constants, after confirming no current SEMS+ endpoint uses them.
- The plugin's `Mode4` branches and dead connection-driven update callback.

Do not remove current SEMS+ methods such as `GoodWeSEMSPlus.powerStationListRequest()`, `_openApiPost()`, `openApiDeviceListRequest()`, `openApiDeviceTelemetryRequest()`, `getWebInverterDevices()`, `getWebInverterTelemetry()`, `getWebInverterTelecounting()`, and `getWebData()`.

## Tests and documentation

- Replace the dual-mode startup and heartbeat tests with tests proving startup always creates the SEMS+ client and heartbeat always schedules the SEMS+ update path, even when legacy stored parameters omit or contain `Mode4="No"`.
- Remove tests whose purpose is to exercise legacy login, station-list, monitor, control, or login-fallback requests.
- Add mocked-request assertions that login failure makes no request to `OLD_LOGIN_URL`, and polling/station discovery never posts to the retired monitor or v3 station-list routes.
- Retain and run the existing SEMS+ request-contract tests for regional URLs, authentication headers/signatures, station discovery, telemetry normalization, and error handling.
- Update `README.md` so setup no longer instructs users to enable SEMS+, and revise `CONTRIBUTING.md` to require SEMS+-only routing with explicit assertions that retired routes are not called.

## Compatibility and risks

- A saved `Mode4` value should be ignored, not treated as a migration error. Removing the selector changes no device-unit layout or stored sensor history.
- Installations whose accounts cannot authenticate to SEMS+ will stop receiving updates; the old API is not a supported fallback. Surface a clear login/API error and document the SEMS+ account requirement.
- Removing the legacy control method may affect callers outside this plugin. Check repository references before deletion and document that the current method is unsupported if no SEMS+ control contract is available.
- Keep this change separate from telemetry mapping, station selection, and energy-counter behavior so API retirement remains reviewable.

## Acceptance criteria

- The plugin contains no user-selectable SEMS+/legacy API flag and always initializes the SEMS+ client.
- No production code sends requests to the retired legacy login, monitor, station-list, or control endpoints.
- A failed SEMS+ login does not trigger a legacy request.
- SEMS+ station discovery and telemetry continue to produce the existing normalized data consumed by the plugin.
- Existing hardware configuration and device history remain usable without manual `Mode4` edits.
- Tests, coverage, manual fake-Domoticz checks, and compilation pass with all legacy-mode expectations removed.
