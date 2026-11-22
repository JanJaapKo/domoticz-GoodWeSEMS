# Design: Battery Support for SEMS+

## Goal

Expose battery readings reported by SEMS+ in Domoticz for hybrid inverters,
without adding empty battery devices to inverters that do not have a battery.
This addresses [issue #60](https://github.com/JanJaapKo/domoticz-GoodWeSEMS/issues/60).

The first implementation should use the station-list measurements observed in
the two attached charging/discharging captures. It should not infer battery
readings from inverter output power or from the inverter's backup-output
telemetry.

## Evidence from issue #60 captures

Both captures call `POST /sems-plant/api/portal/stations/page`. The response
places battery information on each station entry in `data.dataList`, rather
than in the per-inverter `telemetry` or `telecounting` response:

| Field | Charging capture | Discharging capture | Observed meaning |
| --- | ---: | ---: | --- |
| `soc` | 89 | 98 | State of charge, percent |
| `batteryCapacity` | 4.8 | 4.8 | Nominal capacity, kWh |
| `pBat` | -1.0922 | 0.51191 | Battery power, kW; negative is charging, positive is discharging |
| `proCharStatsToday` | 4.8 | 5.3 | Energy charged today, kWh |
| `proDischarStatsToday` | 1.1 | 1.4 | Energy discharged today, kWh |
| `proCharStatsTotal` | 650.4 | 650.9 | Total energy charged, kWh |
| `proDischarStatsTotal` | 605.7 | 606.0 | Total energy discharged, kWh |

The reported `pBat` values correspond in direction and approximate magnitude
to the user's Home Assistant readings at the capture times. They need not
match exactly because readings were taken at different times while power was
changing.

The same station contains a GW3648-EM with `subtype: "store"` and a
GW5000-DT with `subtype: "grid"`. Battery metrics are at station level, so the
station's values must not be copied to every inverter. The storage subtype is
the observed way to distinguish the battery-connected inverter in this
example.

The per-inverter telemetry shown in both captures has no battery voltage,
battery current, BMS status, or power-setpoint field. `backup_parameters`
describes backup AC output and is not battery-terminal telemetry. The current
plugin's normalized `battery`, `battery_power`, and `bms_status` values are
empty because they are not populated from these station-list fields.

## Home Assistant implementation reference

The [goodwe-sems-home-assistant integration](https://github.com/TimSoethout/goodwe-sems-home-assistant)
provides useful mapping precedent:

- [`sensor.py`](https://github.com/TimSoethout/goodwe-sems-home-assistant/blob/5950f0b940ac00d79148022f2c3f927759aa3a03/custom_components/sems/sensor.py)
  defines battery state-of-charge and per-battery power/voltage/current
  sensors, as well as daily and total charge/discharge energy sensors.
- [`sems_api.py`](https://github.com/TimSoethout/goodwe-sems-home-assistant/blob/5950f0b940ac00d79148022f2c3f927759aa3a03/custom_components/sems/sems_api.py)
  converts SEMS+ station-flow `pBat` from kW to W and treats positive as
  discharge and negative as charge. It also handles separate battery-rack
  telemetry when that device data is available.

For this plugin, use the captured station-list contract as the source for this
hybrid-inverter case. Do not assume the Home Assistant battery-rack telemetry
or control endpoints are present in these captures, and preserve the signed
`pBat` value in the requested in/output-power device rather than replacing it
with an absolute magnitude.

## Current plugin path

- `GoodWeSEMSPlus.powerStationListRequest()` already requests the station list
  and returns its `data` object, including `dataList`.
- `plugin.py:getPowerStationIds()` currently reduces that response to station
  IDs. `startDeviceUpdateV2()` then fetches per-inverter data, but the station
  entry containing battery measurements is no longer available to
  `updateDevices()`.
- `getWebData()` creates normalized inverter records from `all-status`,
  telemetry, and telecounting. It currently defaults battery-related inverter
  fields to empty values; the captured station-level fields are not mapped.
- Domoticz inverter devices use the inverter serial number as their stable
  `DeviceID`. Existing units occupy numbers 1 through 24; `Inverter` currently
  reserves 25 units per device.

## Proposed data flow

1. Keep each complete station-list entry, keyed by its validated station ID,
   through the existing polling cycle. Do not discard fields after extracting
   the IDs.
2. Associate the station battery summary with the station's reported
   storage-capable inverter(s), using the all-status device metadata (in
   particular the observed `subtype: "store"`). Do not use inverter `status`
   to determine battery presence; a storage inverter may be waiting or offline
   while its station battery values remain useful.
3. Normalize only finite numeric values. Treat absent, null, malformed, or
   non-finite fields as unavailable; do not convert them to zero and do not
   overwrite a previous Domoticz value with a fabricated zero.
4. Convert `pBat` from kW to W by multiplying by 1000, without reversing its
   sign or taking its absolute value. Keep `soc` in percent and preserve the
   captured energy counters in kWh.
5. Update battery devices independently of inverter production state. A
   `Waiting` inverter with valid station-list battery readings must still
   update its battery sensors. If station discovery or battery values are
   unavailable for a poll, retain previous values and report the failure
   through normal plugin logging.
6. If a station reports more than one storage-capable inverter, do not
   duplicate station-aggregate measurements onto all of them. The API evidence
   does not establish per-inverter allocation; log the ambiguity and leave
   assignment unresolved until a reliable contract or station-scoped device
   design is chosen.

## Domoticz devices

Add units to the existing serial-number inverter device so inverter identity
and historical data remain stable. Allocate new unit numbers after existing
units and increase the reserved unit count; do not reuse existing unit numbers.
The exact type/subtype requests below come from the latest issue comment:

| Name | Requested Domoticz type | Value/source |
| --- | --- | --- |
| Battery percentage | `TypeName="General"`, `Subtype=6` | Station `soc`, percent |
| Battery in/output power | `Type=250`, `Subtype=1` | Station `pBat`, converted to W; negative charges, positive discharges |
| Battery power setpoint | `Type=242`, `Subtype=1` | No source field established by either capture; see open question below |

Also expose the daily energy counters requested in the issue when the reported
fields are valid:

- Battery charge today from `proCharStatsToday` (kWh).
- Battery discharge today from `proDischarStatsToday` (kWh).

The captures also include lifetime charge and discharge counters. Keep these
as optional follow-up units unless the implementation and user confirm they
are in scope for the initial device set. Do not derive energy from instantaneous
power. Daily values can reset at the portal's day boundary, so select Domoticz
device semantics that accommodate that reset rather than treating a daily
counter as a lifetime-increasing total.

Create battery units only when the inverter is identified as storage-capable
and valid battery data is reported. In the captured mixed station, the
GW3648-EM (`store`) gets battery units; the GW5000-DT (`grid`) does not. Do not
create empty battery units for a station/inverter that has no battery.

## Power-setpoint and other unavailable data

The two captures do not contain a battery power setpoint, and they do not
establish that a battery-control endpoint exposes one. A setpoint is not the
same measurement as actual `pBat`. Do not populate the requested setpoint
device with `pBat`, inverter AC power, a guessed default, or a control value
from an unrelated endpoint. Before implementing that unit, confirm whether it
is intended to be a read-only reported target or a writable control, and obtain
a sanitized API capture showing the source and units. Do not add a command
path as part of this read-only telemetry change.

Battery voltage, current, and BMS/mode status were part of the issue's initial
request, but were absent from both per-inverter telemetry captures. Leave them
out of the initial implementation. In particular, do not present backup
voltage/current or the inverter's general state as battery voltage/current or
BMS state.

## Implementation areas

### `GoodWe.py`

- Preserve station-list entries for downstream mapping, or add a clearly
  validated station-battery normalization method while retaining the existing
  station-list response contract.
- Normalize `soc`, `pBat`, daily energy, and optional lifetime energy only
  when the source fields are valid.
- Keep station battery values distinct from per-inverter telemetry fields.
- Do not introduce a success-shaped empty battery response when the station
  list request fails or has an invalid shape.

### `plugin.py`

- Carry the station entry into the station's inverter updates instead of
  passing only the station ID.
- Detect the storage-capable inverter from API device metadata and create/update
  only its battery units.
- Use stable, unused unit numbers and update the unit reservation consistently.
- Keep the latest requested Domoticz types for percentage, in/output power,
  and setpoint, while leaving the setpoint blocked pending source confirmation.
- Update daily counters from their station-list values without confusing daily
  resets with cumulative lifetime energy.
- Preserve existing inverter data, state handling, and energy-counter behavior.

## Focused test plan

All tests should use captured or synthetic sanitized payloads and must not
contact GoodWe services.

1. Parse the charging fixture: `soc=89`, `pBat=-1.0922 kW`, and the four
   charge/discharge counters map with the expected units.
2. Parse the discharging fixture: `soc=98` and `pBat=0.51191 kW`; the result is
   positive `511.91 W`, not an absolute value or negative discharge.
3. A mixed station with one `store` and one `grid` inverter creates/updates
   battery units only on the storage-capable inverter.
4. Missing or invalid battery fields neither create battery units on a
   non-battery inverter nor reset a previously reported value to zero.
5. A storage inverter in `Waiting` state still updates its battery readings.
6. Multiple storage-capable inverters do not each receive a duplicated
   station-level measurement.
7. Battery station-list values are forwarded from the station-list response
   through the update path while existing inverter telemetry updates continue.
8. Device creation uses the requested Domoticz type/subtypes and stable
   serial-number `DeviceID`; all newly allocated unit numbers avoid existing
   units.
9. No setpoint value or battery voltage/current/BMS status is fabricated when
   the API response does not provide it.
10. Daily charge/discharge counters preserve kWh values and tolerate the daily
    reset without being treated as lifetime totals.

## Acceptance criteria

- Battery percentage, signed battery power, and captured daily energy values
  reach Domoticz from the station-list API data.
- Charging is negative and discharging is positive in the battery power unit.
- Battery devices are created only for a storage-capable inverter with
  reported battery data; a grid-only inverter in the same station receives
  none.
- Existing inverter devices and unit numbering/history remain intact.
- Missing battery information does not appear as a healthy zero reading.
- Setpoint and unobserved battery fields remain explicitly unavailable until
  supported API evidence is provided.
