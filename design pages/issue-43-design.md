# Design: Remove the Legacy Monitor Request from SEMS+

## Goal

Stop making the legacy `GetMonitorDetailByPowerstationId` request from `GoodWeSEMSPlus.stationDataRequest()`. The legacy monitor endpoint no longer provides usable data for SEMS+ accounts, so this request adds latency and misleading authorization errors before the plugin reaches its SEMS+ Web API implementation.

Keep the legacy endpoint and behavior in the base `GoodWe` class for installations using the legacy API mode.

## Current behavior

`GoodWeSEMSPlus.stationDataRequest()` currently:

1. Posts to the legacy monitor endpoint.
2. Parses and logs its response.
3. If the response does not contain a non-empty `data.inverter` list, calls `getWebData()` and returns the synthesized station data.
4. Otherwise returns the legacy response.

For SEMS+ accounts where the legacy endpoint consistently returns an authorization error or empty data, step 1 never yields usable inverter readings. The response is already discarded in favor of `getWebData()`, so the request does not provide a useful fallback or result.

## Proposed flow

1. Have `GoodWeSEMSPlus.stationDataRequest(stationId)` call `getWebData(stationId)` directly.
2. Remove the legacy monitor request, payload construction, response parsing, and legacy-specific fallback handling from this SEMS+ override.
3. Preserve the existing normalized return shape from `getWebData()`: a station dictionary containing `info` and an `inverter` list. `stationDataRequestV2()` already accepts this shape.
4. Leave `GoodWe.stationDataRequest()` and its legacy route intact. Legacy-mode behavior remains owned by the base class.

The SEMS+ request path should continue to use the existing SEMS+ token, regional API base, signatures, and Web endpoint helpers. This change should not alter authentication or endpoint request construction.

## Scope and compatibility

- Apply the behavior change only to `GoodWeSEMSPlus.stationDataRequest()`.
- Do not remove or rewrite legacy methods in `GoodWe`.
- Do not change the plugin's mode selection or configuration.
- Do not change the shape consumed by `stationDataRequestV2()`, `createStationV2()`, or `updateDevices()`.
- Avoid unrelated changes to station discovery, telemetry normalization, logging configuration, or API headers.

## Relationship to issue #37

This removes a known-useless request before the SEMS+ Web request and should avoid its repeated delay and legacy authorization error. It does **not** address the reported case where `all-status` returns HTTP 200 with an empty `deviceDetailList`: `getWebData()` still has no serial numbers to use for per-device telemetry and will return a normalized station with zero inverters. That behavior requires a separate design for empty or invalid device-list responses and an independent source of inverter serial numbers.

## Focused tests

1. Mock `getWebData()` and verify `GoodWeSEMSPlus.stationDataRequest()` returns its result for the requested station ID.
2. Verify the SEMS+ method does not call `requests.post()` for the legacy monitor URL.
3. Verify `GoodWe.stationDataRequest()` retains its legacy request behavior.
4. Verify the existing `stationDataRequestV2()` contract accepts the normalized SEMS+ response.

Tests should not contact GoodWe services; use mocks to verify the route and return contract.

## Acceptance criteria

- SEMS+ station refreshes call `getWebData()` without first requesting the legacy monitor endpoint.
- The existing normalized SEMS+ data shape and downstream station/device updates remain compatible.
- Legacy mode continues to use the base-class legacy endpoint.
- An empty `all-status` result remains visible as a separate unresolved condition and is not treated as fixed by this change.

## Risks

The main compatibility risk is accidentally changing shared base-class behavior while removing the SEMS+ request. Keep the edit confined to the `GoodWeSEMSPlus` override and retain a test for the legacy base-class path. A second risk is interpreting this cleanup as a fix for missing inverter readings; the SEMS+ device-list response remains the controlling data source for the current Web fallback.