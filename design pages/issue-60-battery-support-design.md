# Design: Battery Support for SEMS+

## Goal

Expose battery readings reported by SEMS+ in Domoticz for hybrid inverters,
without adding empty battery devices to inverters that do not have a battery.
This addresses [issue #60](https://github.com/JanJaapKo/domoticz-GoodWeSEMS/issues/60).

Use only measurements in the issue captures that map to Home Assistant's
battery sensors. Do not infer battery readings from inverter output power or
from backup-output telemetry.

## Evidence from issue #60 captures

The first charging/discharging captures show station-level summary values and
daily battery counters. The latest capture additionally confirms that the
related `BAT_SYS` telemetry endpoint returns individual battery measurements:

| Field | Captured value | Observed meaning |
| --- | ---: | --- |
| `pBat` | 0.03353 | Battery power, kW |
| `voltage` | 47.9 | Battery voltage, V |
| `a` | 0.7 | Battery current, A |
| `soc` | 9 | State of charge, percent |
| `soh` | 100 | State of health, percent |
| `batSysTemp` | 15.2 | Battery temperature, Celsius |
| `aMaxChar` | 50 | BMS maximum charge current, A |
| `aMaxDischar` | 20 | BMS maximum discharge current, A |
| `proCharStatsToday` | 0.4 | Energy charged today, kWh |
| `proDischarStatsToday` | 1.7 | Energy discharged today, kWh |

The capture's station-flow `soc` and `pBat` agree with the corresponding
battery telemetry values. The same station contains a GW3648-EM with
`subtype: "store"` and a GW5000-DT with `subtype: "grid"`.

The issue's HA implementation has matching per-battery sensors for power,
voltage, current, SoC, SoH, BMS temperature, and BMS charge/discharge current
limits, plus per-inverter battery charge/discharge-today sensors. Do not add
the other HA-only endpoints, station-flow/statistics devices, capacity,
control functions, or unsupported status/setpoint data.

## Home Assistant implementation reference

The [goodwe-sems-home-assistant integration](https://github.com/TimSoethout/goodwe-sems-home-assistant)
provides useful mapping precedent:

- [`sensor.py`](https://github.com/TimSoethout/goodwe-sems-home-assistant/blob/5950f0b940ac00d79148022f2c3f927759aa3a03/custom_components/sems/sensor.py)
  defines battery state-of-charge and per-battery power/voltage/current
  sensors, as well as daily and total charge/discharge energy sensors.
- [`sems_api.py`](https://github.com/TimSoethout/goodwe-sems-home-assistant/blob/5950f0b940ac00d79148022f2c3f927759aa3a03/custom_components/sems/sems_api.py)
  maps related battery telemetry into per-battery sensors and maps daily
  charge/discharge counters into per-inverter sensors.

Use the captured `BAT_SYS` telemetry and inverter telecounting fields for
these matching sensors. Convert `pBat` from kW to W and preserve its sign:
negative is charging and positive is discharging.

## Current plugin path

- `getWebData()` creates normalized inverter records from `all-status`,
  telemetry, and telecounting.
- Storage-capable inverters use `relatedDevices` to discover `BAT_SYS` battery
  serials, then query each battery's telemetry. Individual endpoint failures
  must not prevent normal inverter updates.
- Battery charge/discharge-today values come from the inverter's existing
  telecounting response.
- Domoticz inverter devices use the inverter serial number as their stable
  `DeviceID`. Existing units occupy numbers 1 through 24; new battery units
  start at 25.

## Proposed data flow

1. Use all-status metadata (`subtype: "store"` or the storage-integrated
   cabinet device type) to identify battery-capable inverters, independent of
   their generating/waiting/offline status.
2. Discover connected `BAT_SYS` devices and query their own telemetry; do not
   copy station aggregates to every inverter.
3. Normalize only finite numeric values. Treat absent, null, malformed, or
   non-finite fields as unavailable; do not convert them to zero and do not
   overwrite a previous Domoticz value with a fabricated zero.
4. Convert battery `pBat` from kW to W without reversing its sign. Preserve
   SoC/SoH percentages, voltage/current/temperature, and daily energy units.
5. Update battery devices independently of inverter production state. A
   `Waiting` inverter must still update valid battery readings. If an optional
   battery endpoint fails, retain prior values and report the failure.

## Domoticz devices

Add daily battery charge/discharge units to the inverter's serial-number
device, and one sensor block per connected `BAT_SYS` device for power, voltage,
current, SoC, SoH, temperature, and BMS maximum charge/discharge current. Use
stable unused unit numbers after existing units and create units only when the
source value is available. Preserve daily energy values as kWh rather than
treating them as lifetime-increasing counters.

| Name | Requested Domoticz type | Value/source |
| --- | --- | --- |
| Battery percentage | `TypeName="General"`, `Subtype=6` | `soc`, percent |
| Battery in/output power | `Type=250`, `Subtype=1` | `pBat`, W; negative charges, positive discharges |
| Battery voltage/current | Voltage/current sensor types | `voltage` in V and `a` in A |
| Battery SoH and temperature | General percentage and temperature sensor | `soh` in percent and `batSysTemp` in Celsius |
| BMS current limits | Current sensor type | `aMaxChar` and `aMaxDischar`, A |
| Battery charge/discharge today | Custom `kWh` sensors | `proCharStatsToday` and `proDischarStatsToday` |

Create battery units only when the inverter is identified as storage-capable
and valid battery data is reported. In the captured mixed station, the
GW3648-EM (`store`) gets battery units; the GW5000-DT (`grid`) does not. Do not
create empty battery units for a station/inverter that has no battery.

## Power-setpoint and other unavailable data

Do not add the requested battery power-setpoint unit: the issue capture has no
source for it, and the reported HA function menus are controls, not telemetry.
Also leave station-level flow/statistics, capacity, and other HA-only/control
entities out. Do not present inverter backup voltage/current or inverter
state as battery measurements.

## Implementation areas

### `GoodWe.py`

- Normalize HA-mapped fields from connected `BAT_SYS` devices and battery
  charge/discharge today from inverter telecounting, accepting only valid
  finite numbers.
- Keep optional battery endpoint failures separate from required inverter
  telemetry failures.

### `plugin.py`

- Detect the storage-capable inverter from API device metadata and create/update
  only its battery units.
- Use stable, unused unit numbers for battery sensors and daily charge/discharge.
- Preserve existing inverter data, state handling, and energy-counter behavior.

## Focused test plan

All tests should use captured or synthetic sanitized payloads and must not
contact GoodWe services.

1. Map the captured `BAT_SYS` power, voltage, current, SoC, SoH, temperature,
   and BMS current limits into the matching HA sensor devices.
2. Convert signed `pBat` to W without changing its sign; map daily charge and
   discharge counters in kWh.
3. A mixed station with one `store` and one `grid` inverter creates/updates
   battery units only on the storage-capable inverter.
4. Missing or invalid battery fields neither create battery units on a
   non-battery inverter nor reset a previously reported value to zero.
5. A storage inverter in `Waiting` state still updates its battery readings.
6. Device creation uses the requested Domoticz type/subtypes and stable
   serial-number `DeviceID`; all newly allocated unit numbers avoid existing
   units.
7. Unsupported setpoint/control entities and unrelated HA station devices are
   not created.

## Testing this branch on a Raspberry Pi

The `feature/battery-support` branch must be pushed to GitHub before it can be
checked out on the Pi. From the existing plugin clone on the Pi, fetch and
check out the branch once:

```bash
cd ~/domoticz/plugins/domoticz-GoodWeSEMS
git fetch origin feature/battery-support
git checkout --track -b feature/battery-support origin/feature/battery-support
```

For later updates to the same branch:

```bash
cd ~/domoticz/plugins/domoticz-GoodWeSEMS
git checkout feature/battery-support
git pull --ff-only origin feature/battery-support
```

Keep the Pi's `.env` file local and untracked. Run
`python3 telemetry_manual_test.py` from the plugin directory, optionally set
`STATION_ID` to test one station. The script also queries the read-only
station-flow, station-statistics, related battery-device, battery telemetry,
and battery-state endpoints used by Home Assistant; it does not issue battery
control commands. Share the output only after masking station IDs,
inverter/battery serial numbers, station names, addresses, and other
identifying data.

## Acceptance criteria

- HA-mapped battery telemetry and daily energy values reach Domoticz from the
  related-device telemetry and inverter telecounting APIs.
- Charging is negative and discharging is positive in the battery power unit.
- Battery devices are created only for a storage-capable inverter with
  reported battery data; a grid-only inverter in the same station receives
  none.
- Existing inverter devices and unit numbering/history remain intact.
- Missing battery information does not appear as a healthy zero reading.
- Setpoint and unobserved battery fields remain explicitly unavailable until
  supported API evidence is provided.
