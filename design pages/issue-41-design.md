# Design: Handle SEMS+ inverter payloads that omit the name field

## Goal

Prevent startup crashes when the SEMS+ station payload contains inverter records without the expected `name` field, while also improving the logging and diagnostics around the failure.

This design addresses the root cause observed in the issue #41 logs: the plugin authenticates successfully, discovers the station, and then crashes when it creates inverter model objects from a response where the `inverter` data no longer matches the older contract.

## Summary of the root cause

The crash is not caused by a broken login or by a missing station ID. The failure occurs later in the model-building path:

- `GoodWeSEMSPlugin.startDeviceUpdateV2()` calls `self.goodWeAccount.createStationV2(DeviceData)` after a successful token refresh and station lookup.
- `GoodWe.py` creates a `PowerStation` object from the incoming station payload.
- `PowerStation.__init__()` calls `self.createInverters(stationData["inverter"])`.
- `createInverters()` does `self.inverters[inverter['sn']] = Inverter(inverter)`.
- `Inverter.__init__()` currently assumes every inverter record contains `inverterData["name"]`.
- The attached issue log shows the actual payload structure now includes a valid serial number but no `name` key, which raises `KeyError: 'name'` and aborts startup.

This means the plugin is coupled to an older SEMS payload shape. The API contract has drifted, and the code path is not defensive enough to handle the new response envelope.

## Evidence from the logs

The log confirms the sequence:

1. Login succeeds and a token is obtained.
2. Power station selection succeeds.
3. The legacy monitor endpoint returns `{ "data": {} }` and the plugin falls back to SEMS+ web endpoints.
4. A web request to the inverter device list succeeds and returns data for one inverter.
5. The plugin then crashes while building the in-memory inverter model.

This is the critical clue: the failure is not at the HTTP layer; it is at the data-normalization layer, right after a successful API call.

## Why the current code fails

The relevant code path is in [GoodWe.py](../GoodWe.py):

- `PowerStation.__init__()` expects `stationData["info"]["stationname"]`, `stationData["info"]["address"]`, and `stationData["info"]["powerstation_id"]`.
- `Inverter.__init__()` expects `inverterData["name"]` and `inverterData["sn"]`.
- The new API response is not guaranteed to include every legacy field.

This makes the implementation brittle to contract changes even when the API itself is healthy. The plugin design assumes a strict response structure and fails fast on missing keys instead of normalizing or tolerating partial data.

## Design goals

1. Handle both legacy and current SEMS+ data shapes without crashing.
2. Preserve compatibility with current behavior where the response includes `name`.
3. Make missing or optional inverter fields degrade gracefully.
4. Improve logging so real API failures are visible in the plugin log rather than only in Domoticz output.
5. Keep the fix localized to the model-building layer so the rest of the polling flow remains stable.

## Proposed changes

### 1) Add a defensive normalizer for inverter data

Introduce a helper in the model layer that converts incoming inverter records into a stable internal shape.

Example responsibility:

- read `sn` as the primary identifier
- read `name` if present
- otherwise fall back to a known alternative field such as `deviceName`, `title`, or `model`
- if no human-readable name is present, use the serial number as a display fallback
- if required fields are still missing, log a warning and continue with a placeholder name

This prevents `KeyError` and keeps the plugin alive even when the upstream API omits optional metadata.

### 2) Harden `PowerStation` creation

`PowerStation.__init__()` should validate its input before indexing deep into `stationData["info"]` and `stationData["inverter"]`.

The station object should:

- accept missing `stationname` or `address` without crashing
- log a warning when metadata is incomplete
- continue creating the station with safe placeholders
- only call `createInverters()` when `inverter` is a list, otherwise log and return an empty station model

This turns response drift from a crash into a recoverable condition.

### 3) Add structured fallback logging

The issue also highlights a second problem: the plugin writes a lot of useful debug noise to the root logger, but real Python exceptions are surfaced in Domoticz instead of the plugin file log. The fix should ensure:

- a dedicated plugin logger is created once and reused
- the logger is configured from the plugin lifecycle, not the root logger
- missing-field warnings are recorded in the file log with enough context to diagnose API drift
- the log message distinguishes between:
  - expected optional field missing
  - response contract mismatch
  - fatal authentication or request failure

This will make future API changes obvious without relying only on Domoticz’s error surface.

### 4) Keep compatibility with the old response contract

The implementation should not assume the new format replaces the old one. The model should accept both shapes:

- legacy payloads with `name`
- newer payloads with alternative naming or missing human labels

The internal representation should remain consistent, so the rest of the plugin does not care which API version produced the payload.

## Proposed implementation outline

### Model-layer changes

In [GoodWe.py](../GoodWe.py):

- add a helper to normalize inverter records before creating `Inverter`
- add a helper to resolve a safe station name and address when the response is partially empty
- guard `createInverters()` against non-list payloads and missing keys
- ensure `PowerStation` can be created from a valid station object even when metadata is incomplete

### Logging-layer changes

In [plugin.py](../plugin.py):

- configure a dedicated logger name such as `GoodWeSEMS`
- stop mutating the global root logger
- avoid duplicate file handlers on restart
- emit warnings for missing metadata and debug details for request lifecycle

### Compatibility and safety rules

- never log tokens, passwords, or raw authorization headers
- keep the `name` fallback deterministic and human-readable
- never crash on a missing optional field; degrade to a placeholder value
- keep the log output concise and targeted to the event, not a full raw payload dump

## Focused test strategy

Add tests for the following cases:

1. Legacy inverter payload with `name` present.
2. Newer inverter payload with `sn` but no `name`.
3. Payload with `sn` and a fallback name field such as `deviceName`.
4. Payload with `sn` and no name at all; ensure the model uses the serial number and logs a warning.
5. Station payload where `info` is missing or partially present.
6. Non-list `inverter` data; ensure the station is created empty instead of crashing.

## Acceptance criteria

The fix is complete when all of the following are true:

- a station with inverter data lacking `name` no longer crashes the plugin
- the plugin starts and continues polling instead of failing hard
- the user sees a clear warning in the file log about partial or missing inverter metadata
- the logging configuration is clean and does not duplicate root handlers
- the code remains compatible with both old and new SEMS payloads

## Risk assessment

The main risk is silent data loss if the plugin chooses a placeholder name and the UI or downstream logic expects a real display name. To reduce that risk, the fallback should be explicit and the log should clearly identify the fallback path. This makes the system resilient without hiding the underlying API drift.

## Recommendation

Proceed with the defensive normalization fix first. It addresses the actual root cause and keeps the plugin running even when the upstream API shape changes again. The logging cleanup is a secondary but important follow-up because it helps operators diagnose similar contract drift quickly and prevents the same issue from being disguised as a generic Domoticz crash.
