# Design: Automatic Power Station ID Discovery

## Goal

Resolve a user's Power Station ID through `GetPowerStationList` so initial setup no longer requires copying the ID from a SEMS portal URL. For accounts with multiple stations, use the first station, as specified in issue #39.

## Current behavior

- `plugin.py` exposes `Mode1` as a required Power Station ID and refuses startup or polling when it is empty.
- After authentication, `startDeviceUpdateV2()` passes that configured value to `stationDataRequestV2()`.
- The API request and response handling live in `GoodWe.py`; the SEMS+ implementation already centralizes authenticated POST requests and response validation there.

## Proposed flow

1. Authenticate using the existing account flow.
2. Request the station list through a new account-layer method for `POST https://eu.semsportal.com/api/v3/PowerStation/GetPowerStationList` (derive the regional host from the configured SEMS server rather than hard-coding Europe).
3. Validate the response and select the first entry with a non-empty `PowerStationId`.
4. Keep the selected ID on the account/plugin instance and pass it to the existing `stationDataRequestV2()` call. Reuse it for heartbeat updates instead of querying the station list on every poll.
5. If the request fails, the response is malformed, or no station has an ID, log and report a clear error and skip the telemetry update. Do not silently fall back to a manually configured ID.

The station lookup belongs in `GoodWe.py` next to the other authenticated API methods. `plugin.py` should own the startup/polling sequence and no longer gate execution on `Mode1` being populated.

## Configuration and compatibility

- Remove the Power Station ID input and the instructions for copying it from the portal URL.
- Continue to ignore an existing stored `Mode1` value so upgrades from installations that already have an ID require no manual cleanup. If Domoticz requires the parameter to remain declared, keep it hidden or optional during the transition; do not use it as a fallback.
- Update the README limitation that currently says the ID is mandatory. The one-station-per-plugin limitation remains; the selected station is the first one returned by SEMS.

## Request contract to verify before implementation

Issue #39 identifies the endpoint and response field, but does not include the POST body, required headers, or a sample response. Capture or obtain the current SEMS request contract before coding those details. Reuse the existing authenticated token/header helpers where compatible, and route the request to the configured region. Avoid logging credentials or token values.

Expected response handling should tolerate the documented envelope, require a list of station records, and extract `PowerStationId` from the first usable record. The exact envelope path should follow the verified response rather than assumptions in this design.

## Focused tests

- The station-list method posts to the correct regional endpoint with the verified request body and authentication headers.
- It returns the first valid `PowerStationId` when multiple stations are present.
- Empty station lists, missing IDs, malformed responses, and HTTP/API failures produce a clear failure without calling the telemetry endpoint.
- Plugin startup and heartbeat use the resolved ID and do not require `Mode1`.
- Existing configured `Mode1` values are ignored, and the existing telemetry request contract remains unchanged.