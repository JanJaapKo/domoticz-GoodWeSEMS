# Design: Support Multiple SEMS+ Power Stations

## Goal

Support every power station returned for the configured SEMS+ account from one
Domoticz hardware instance by default. For backwards compatibility, users may
optionally provide a power station ID in `Mode1` to restrict device creation and
updates to that station. Each station's inverters remain represented by stable
Domoticz devices identified by inverter serial number. This addresses
[issue #51](https://github.com/JanJaapKo/domoticz-GoodWeSEMS/issues/51).

## Current behavior and existing preparation

- `GoodWeSEMSPlus.powerStationListRequest()` requests
  `/sems-plant/api/portal/stations/page` with `current=1` and `size=100`.
- `plugin.py:getPowerStationId()` accepts an existing saved `PowerStationId`
  first, otherwise parses the station-list response and selects one ID. That
  saved value can permanently hide the other stations after this feature ships.
- `startDeviceUpdateV2()` requests telemetry for just that selected ID.
- `_GoodWeAccountBase.createStationV2()` stores the resulting model at key `1`,
  and `updateDevices()` reads that same fixed key.
- `getWebData(stationId)` and the telemetry endpoints already accept an explicit
  station ID. These can be reused for each discovered station.
- `PowerStation` and `Inverter` already model station IDs and inverter serial
  numbers. `plugin.py:createDevices()` already uses the inverter serial as
  `Domoticz.DeviceID`, and includes the serial in unit names. Thus devices for
  distinct inverter serials can coexist; the main missing behavior is processing
  every station rather than only the first.
- Device units have stable unit numbers within each inverter device. This design
  should not allocate units by station index.

## Proposed flow

1. Authenticate using the existing SEMS+ login and token-refresh behavior.
2. Request all station-list pages through
   `GoodWeSEMSPlus.powerStationListRequest()`. Respect the API's actual
   pagination/total-count fields, preserve regional routing, and verify the
   response contract before relying on field names. Do not assume the first
   page contains every station.
3. Normalize station-list entries into a unique, ordered collection of usable
   station IDs. Ignore duplicate IDs. If `Mode1` is non-empty, poll only the
   matching station ID; if it is empty, poll every discovered station. A
   configured ID not present in the response is an explicit error, not a reason
   to silently poll all stations.
4. For each selected station ID, request station telemetry and normalize it
   through the existing `stationDataRequestV2()` / `getWebData()` path.
5. Keep each station model associated with its actual station ID. Replace the
   single fixed station key with an ID-keyed model collection, or pass the
   relevant `PowerStation` explicitly into device updates. Do not let one
   station's model overwrite another's.
6. Update each station's inverters using their serial numbers as the stable
   Domoticz device identifiers. Keep existing device/unit names, unit numbers,
   sensor mappings, energy counters, and per-inverter update behavior.
7. Continue to the next station after a station-specific telemetry failure,
   while logging and surfacing which station failed. Authentication/token
   failures should use the existing refresh/error behavior and must not be
   reported as successful empty updates.

Station discovery should be refreshed periodically so newly-added stations are
eventually included and removed stations stop being polled. Reuse the existing
poll interval initially unless API behavior or rate limits show that a separate
discovery cadence is required. Confirm the station-list endpoint's pagination,
rate limits, and session-expiry behavior before implementation.

## Identity and Domoticz compatibility

- **Station identity:** use the station ID returned by SEMS+ only to scope API
  calls and associate the in-memory station model.
- **Device identity:** preserve `DeviceID=serialNumber` for inverters. This
  preserves existing Domoticz device history when an installation previously
  polled that inverter as the first station.
- **Device naming:** keep the serial number visible in the device/unit names.
  Do not prefix the station ID into device IDs or unit names for normal unique
  inverter serials.
- **Duplicate serials:** check whether serial numbers are guaranteed unique
  across one account. If the same serial appears under more than one station,
  do not silently let one station overwrite the other's devices or telemetry.
  Verify the API/domain contract and define a deterministic, backward-compatible
  collision policy before implementation. Any composite-ID fallback must be
  limited to actual collisions so existing device history remains intact.
- **Configuration migration:** restore `Mode1` as an optional power-station-ID
  filter. When blank, discover and process every station. Do not use the old
  persisted `PowerStationId` value as a filter or source of truth.
- **Single-station accounts:** behavior and device identities remain unchanged
  when SEMS+ returns only one station.
- **Existing data:** do not delete devices or Domoticz history for stations
  absent from a later response. Stopping updates is safer than automatic device
  deletion; report the discovered/polled station set clearly enough to diagnose
  account changes.

## Implementation areas

### `GoodWe.py`

- Extend `powerStationListRequest()` to page through the complete response using
  the verified SEMS+ pagination contract; retain its current regional,
  signature, session-refresh, and API-error handling.
- Keep station-list normalization close to the account API layer, or expose a
  typed/validated station collection to the plugin. Do not silently convert a
  malformed response into an empty successful list.
- Change `_GoodWeAccountBase.createStationV2()` and the account model storage so
  station models are keyed by their real station IDs, not a constant `1`.
- Preserve one `PowerStation` per station and its own inverter map. Ensure a
  station with no valid inverters does not erase or prevent updates for other
  stations.

### `plugin.py`

- Replace `getPowerStationId()` and the one-station startup/update sequence with
  discovery and processing of all station IDs, optionally filtered by `Mode1`.
- Make the station context explicit in model creation and `updateDevices()`; do
  not rely on `powerStationList[1]`.
- Keep inverter device creation/update keyed by serial number and keep existing
  unit mapping, three-phase handling, energy-counter safeguards, and conditional
  sensor creation.
- Isolate station-specific errors so a bad response for one station does not
  block later stations. Keep account-wide authentication and discovery errors
  explicit.
- Remove the `PowerStationId` cache/configuration dependency. Document `Mode1`
  as optional and explain that blank means all stations.

### Documentation

- Update the plugin description and README feature/limitation text: state that
  one hardware instance polls all power stations on the SEMS+ account and
  creates inverter devices identified by serial number.
- Explain the change from the former one-station behavior and the optional
  `Mode1` filter.

## Full compliance and acceptance matrix

| Area | Required behavior |
| --- | --- |
| Discovery | Every station is found, including stations beyond the first API page. |
| Parsing | Valid station IDs are normalized; duplicate IDs are requested only once. |
| API routing | Requests use the configured SEMS+ region and existing authentication/signature conventions. |
| Refresh | Expired-session responses follow the existing login-refresh retry path without skipping stations silently. |
| Data isolation | Each station is queried with its own ID and kept in its own model; no fixed-index overwrite remains. |
| Inverter identity | Distinct inverter serials map to distinct stable Domoticz devices; prior serial-based device history is preserved. |
| Device content | Existing per-inverter units and mappings are retained, including optional PV strings and AC phases. |
| Energy safety | Empty/zero SEMS+ records do not reset prior counters; one station's record cannot update another station's device. |
| Failure isolation | A station-specific failure is logged with station context and does not prevent processing other stations. Account-wide failures remain visible. |
| Account changes | New stations are discovered on a later refresh; removed stations are no longer polled, and their historical devices are not deleted. |
| Legacy configuration | A saved `PowerStationId` cannot limit the new flow; only an explicitly configured `Mode1` filters stations. |
| Single station | One-station accounts retain existing devices, names, update frequency, and behavior. |
| Duplicate serials | Any serial collision is detected and handled by an explicit tested policy rather than overwritten silently. |
| Logging | Logs identify station ID/name and inverter serial where useful, without exposing credentials, tokens, or raw authorization headers. |

## Focused test plan

### Station-list API tests

1. A one-page response returns all valid stations.
2. A multi-page response requests every page and returns every station exactly
   once, including the final partial page.
3. Empty, malformed, missing-ID, and API-error responses produce explicit
   failures; telemetry is not called with an empty or fabricated ID.
4. Duplicate station entries do not cause duplicate telemetry requests.
5. Regional URL, headers/signature, pagination request parameters, and the
   existing single-session-refresh behavior are verified with mocks.

### Plugin and model tests

1. One poll discovers two or more station IDs and calls telemetry once per ID.
2. Models for multiple stations coexist and each model contains only its own
   inverter serials.
3. Inverters from all selected stations create/update distinct serial-keyed Domoticz
   devices, and existing device/unit history is reused.
4. A station-specific request or response failure does not prevent the next
   station from updating; account-wide discovery/authentication failures remain
   visible.
5. A stale persisted `PowerStationId` does not restrict discovery; empty `Mode1`
   polls all stations and a configured `Mode1` polls only its matching station.
6. A newly-added station appears after discovery refresh; a removed station is
   no longer requested without deleting its existing Domoticz devices.
7. Existing energy-counter protection, optional sensor creation, offline
   inverter behavior, and AC/PV mappings still pass across station boundaries.
8. One-station and duplicate-serial cases exercise the compatibility and
   collision policies explicitly.

Run the focused plugin tests and the full existing test suite after
implementation. Add a fake-Domoticz integration test that drives one update
with multiple station responses and asserts the resulting device IDs and
station-specific update values.

## Risks and decisions to verify before implementation

- Confirm the live SEMS+ station page's total/page metadata and maximum page
  size. A hard-coded first-page request cannot meet the all-stations requirement.
- Confirm whether inverter serial numbers are unique per account. The required
  stable serial-based device IDs make collisions important for data integrity
  and backwards compatibility.
- Determine whether partial station-list failures can be distinguished from a
  genuinely complete list. Never interpret a failed later page as a complete
  account result.
- Confirm API rate limits before selecting the discovery refresh cadence. If
  discovery on every telemetry poll is excessive, use an explicit bounded cache
  and refresh it periodically while still detecting newly-added stations.
- Process stations sequentially unless the API and Domoticz framework are
  verified safe for concurrent calls. Concurrency is not needed for correctness.

## Out of scope

- Selecting arbitrary subsets of stations in hardware configuration; `Mode1`
  supports either all stations or one specific station.
- Requiring users to copy station IDs from a portal URL.
- Creating separate Domoticz hardware instances or per-station credentials.
- Deleting orphaned Domoticz devices or rewriting existing sensor history.
- Changing telemetry endpoint contracts or unrelated inverter sensor mappings.
