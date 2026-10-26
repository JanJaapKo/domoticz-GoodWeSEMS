# Design: Detailed Inverter Error Logging

## Goal

Make a GoodWe inverter's reason for entering status `2` (`error`) visible in
Domoticz logs when SEMS+ supplies diagnostic details. When the API supplies no
reason, log that fact explicitly so a future incident still leaves useful
evidence. This design does not infer a fault cause from status or power values.

## Findings

- This plugin maps status `2` to `error` in `GoodWe.py` and logs the numeric
  status and label in `plugin.py:updateDevices()`.
- `GoodWeSEMSPlus.getWebInverterDevices()` copies the per-device `detailMap`
  fields and adds the status from `statusDetailList`. `getWebData()` then merges
  device details with telemetry and counters.
- `getWebData()` currently supplies an empty `fault_message` when the field is
  missing. `plugin.py:updateDevices()` logs `fault_message` only when it is
  non-empty. It does not currently log other diagnostic fields.
- The maintained
  [Home Assistant integration](https://github.com/TimSoethout/goodwe-sems-home-assistant)
  maps inverter status `2` to the generic label `Fault` in
  [`const.py`](https://github.com/TimSoethout/goodwe-sems-home-assistant/blob/master/custom_components/sems/const.py)
  and exposes the status through its sensor platform. That mapping does not
  explain why an inverter is in fault.
- A Home Assistant test fixture,
  [`20250623_homekit_getData.json`](https://github.com/TimSoethout/goodwe-sems-home-assistant/blob/master/tests/test-data/20250623_homekit_getData.json),
  demonstrates that a SEMS response can contain `fault_message` and an `errors`
  list with fields such as `error_code`, `error_id`, `error_type`, and `show`.
  Another fixture has an empty `errors` list. These examples show that details
  may be available, not that every inverter or the plugin's current SEMS+ Web
  endpoints return them. The Home Assistant status mapping is therefore useful
  prior art for naming the state, but not an implementation of detailed error
  logging that can simply be copied.

## Proposed behavior

1. Preserve the existing status mapping and Domoticz inverter-state device.
2. For each inverter update, retain diagnostic values that are actually present
   in the SEMS+ response, including `fault_message`, `warning_code`, and a
   structured `errors` list when available. Do not replace a supplied value
   with an empty default.
3. When status is `2`, log a concise warning that includes the status code and
   label and any available diagnostic fields. Include the inverter serial using
   the existing logging convention.
4. If status is `2` but no usable detail is present, log an explicit
   "no fault details provided by SEMS+" message. Do not manufacture a reason,
   interpret an unknown code, or treat missing details as a successful
   explanation.
5. Log the detailed error message when an inverter first enters status `2` or
   when its diagnostic details change. Retain the existing status logging and
   avoid repeating an identical detailed warning on every poll. An in-memory
   per-inverter diagnostic signature is sufficient; after plugin restart, log
   the active fault again.
6. Log only a whitelist of diagnostic fields, not the full API response,
   credentials, tokens, or unrelated device detail. Keep the raw status code
   alongside its label, including for unknown codes.
7. Do not add another SEMS+ request or retry solely for error details unless
   observation or captured, redacted responses establish that a separate
   endpoint is required and available.

Example messages:

```text
GoodWe inverter (SN: <serial>): status 2 (error); fault_message='...'; errors=[...]
GoodWe inverter (SN: <serial>): status 2 (error); no fault details provided by SEMS+
```

The exact structured fields included in the first message depend on what the
current API response provides. An absent `errors` list is not itself an error,
and an empty list should not be logged as if it contained a fault code.

## Implementation areas

### `GoodWe.py`

- Inspect the current `all-status` device detail and telemetry response shapes
  for fault and warning fields.
- Preserve and normalize only verified diagnostic fields through
  `getWebData()`. Accept optional fields without requiring them for ordinary
  telemetry.
- Keep request count, authentication, retries, and the existing status fallback
  behavior unchanged.

### `plugin.py`

- Centralize the error-state detail formatting/logging near `updateDevices()`.
- Emit a warning to both the plugin logger and Domoticz's log when status is
  `2`; distinguish present diagnostic fields from unavailable details.
- Suppress repeated identical detailed warnings per inverter while retaining
  the current status log and ensure a changed code/message is logged.
- Reset the cached error signature when an inverter is no longer in error.

## Scope and compatibility

- Do not change the meaning of existing statuses or infer `error` from zero
  power, missing telemetry, or a warning code.
- Do not add or renumber Domoticz devices/units in this logging change.
- Do not make optional diagnostic fields mandatory, change API polling cadence,
  or expose raw response bodies.
- Keep all existing fault-message logging behavior for non-empty messages,
  avoiding duplicate messages when the new detailed warning is emitted.

## Focused tests

1. An inverter with status `2`, a `fault_message`, and an `errors` list produces
   a detailed warning containing the provided code/message and status label.
2. An inverter with status `2` but no diagnostic fields produces an explicit
   missing-details warning; it does not invent a fault reason.
3. Optional fields are preserved from the device response through
   `getWebData()` and do not affect telemetry normalization when absent.
4. Identical error details do not create repeated detailed warnings on each
   poll; a changed code/message and a new error after recovery are logged.
5. Status `0`, `1`, and offline/unknown statuses retain their existing
   behavior, including no false fault warning.
6. Logged content is limited to the approved diagnostic fields and does not
   include response bodies, credentials, or tokens.

Tests must use mocked SEMS+ responses and must not contact GoodWe services.

## Acceptance criteria

- A subsequent status-`2` event leaves a Domoticz-visible diagnostic log entry
  with the error code/message when SEMS+ supplies one.
- When SEMS+ supplies no diagnostic detail, logs make that absence explicit.
- Repeated polls with an unchanged fault do not flood the detailed error log;
  changed fault details are recorded.
- Existing state/device mappings and polling behavior remain unchanged.
- The implementation does not claim that a generic status label or an empty
  details response identifies the underlying physical cause.

## Open question before implementation

Verify, using a redacted response captured from an inverter in status `2`,
whether the current `all-status` endpoint includes `errors`, `fault_message`,
or equivalent detail fields. If it does not, first identify and validate a
supported SEMS+ endpoint that supplies the reason. Until then, status and the
absence of a reason can be logged reliably, but a specific root cause cannot
be promised.
