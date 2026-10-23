"""Manually verify SEMS+ power station discovery and live telemetry.

Fill in the configuration values below, then run:

    python telemetry_manual_test.py
"""

import json
import logging
import sys, os

import GoodWe as goodwe_module
from GoodWe import GoodWeSEMSPlus

# Set these values before running the script.
SEMS_USERNAME = ""
SEMS_PASSWORD = ""
# Optional: set a station ID to query only that station. Leave empty to query
# every station returned by the SEMS+ station-list endpoint.
STATION_ID = ""
SEMS_SERVER = "eu.semsportal.com"
logger = None


def get_station_records(response):
    """Extract station records from the response returned by the account API."""
    station_data = response.get("data", response) if isinstance(response, dict) else response
    if isinstance(station_data, list):
        return station_data
    if isinstance(station_data, dict):
        for key in ("dataList", "powerStationList", "PowerStationList", "list"):
            records = station_data.get(key)
            if isinstance(records, list):
                return records
        if station_data.get("PowerStationId") or station_data.get("id"):
            return [station_data]
    raise ValueError("Power station list response did not contain a station list")


def get_station_id(station):
    if not isinstance(station, dict):
        return None
    station_id = station.get("PowerStationId") or station.get("id")
    return station_id.strip() if isinstance(station_id, str) and station_id.strip() else None


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logger = logging.getLogger('root')
    log_filename = "goodwe manual test.log"
    log_format = '%(asctime)s - %(levelname)-8s - %(filename)-18s - %(message)s'
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    # Ensure a file handler is always created for this plugin log file.
    for handler in list(root_logger.handlers):
        if isinstance(handler, logging.FileHandler) and os.path.abspath(getattr(handler, 'baseFilename', '')) == os.path.abspath(log_filename):
            root_logger.removeHandler(handler)
    file_handler = logging.FileHandler(log_filename)
    file_handler.setFormatter(logging.Formatter(log_format))
    file_handler.setLevel(root_logger.level)
    root_logger.addHandler(file_handler)

    username = SEMS_USERNAME.strip()
    password = SEMS_PASSWORD
    station_id = STATION_ID.strip()
    missing = [
        name
        for name, value in (
            ("SEMS_USERNAME", username),
            ("SEMS_PASSWORD", password),
        )
        if not value
    ]
    if missing:
        print("Set these script variables before running: " + ", ".join(missing), file=sys.stderr)
        return 2

    account = GoodWeSEMSPlus(
        SEMS_SERVER,
        "443",
        username,
        password,
    )

    print("===== Requesting SEMS+ access token... =====")
    account.tokenRequest()
    if not account.tokenAvailable:
        print("Token request failed; check the SEMS+ server and account credentials.", file=sys.stderr)
        return 1

    original_get = goodwe_module.requests.get
    original_post = goodwe_module.requests.post

    def print_response(method, original_request):
        def request_and_print(*args, **kwargs):
            response = original_request(*args, **kwargs)
            try:
                response_body = response.json()
            except Exception:
                response_body = response.text
            print(f"\n===== {method} {response.url} (HTTP {response.status_code}) =====")
            print(json.dumps(response_body, indent=2, sort_keys=True, default=str))
            return response
        return request_and_print

    goodwe_module.requests.get = print_response("GET", original_get)
    goodwe_module.requests.post = print_response("POST", original_post)
    try:
        print("===== Requesting SEMS+ power station list... =====")
        station_response = account.powerStationListRequest()
        print("\n===== Station list returned by GoodWeSEMSPlus.powerStationListRequest() =====")
        print(json.dumps(station_response, indent=2, sort_keys=True, default=str))

        station_records = get_station_records(station_response)
        stations_by_id = {}
        for station in station_records:
            discovered_id = get_station_id(station)
            if discovered_id:
                stations_by_id.setdefault(discovered_id, station)

        if not stations_by_id:
            print("SEMS+ returned no power stations with a usable ID.", file=sys.stderr)
            return 1

        print("\n===== Discovered power stations =====")
        for discovered_id, station in stations_by_id.items():
            name = (
                station.get("stationName")
                or station.get("stationname")
                or station.get("name")
                or "(name not returned)"
            )
            print(f"{discovered_id}: {name}")

        if station_id:
            if station_id not in stations_by_id:
                print(
                    f"Configured STATION_ID '{station_id}' was not returned by SEMS+.",
                    file=sys.stderr,
                )
                return 1
            selected_stations = {station_id: stations_by_id[station_id]}
        else:
            selected_stations = stations_by_id

        failures = []
        for selected_id in selected_stations:
            print(f"\n===== Querying Domoticz telemetry for station {selected_id}... =====")
            try:
                station_data = account.stationDataRequestV2(selected_id)
            except Exception as error:
                logger.exception("SEMS+ telemetry request failed for station %s", selected_id)
                print(f"SEMS+ telemetry request failed for station {selected_id}: {error}", file=sys.stderr)
                failures.append(selected_id)
                continue

            if not isinstance(station_data, dict):
                print(f"SEMS+ returned no telemetry data for station {selected_id}.", file=sys.stderr)
                failures.append(selected_id)
                continue

            print(f"\n===== Normalized station data passed to Domoticz ({selected_id}) =====")
            print(json.dumps(station_data, indent=2, sort_keys=True, default=str))
            inverters = station_data.get("inverter", [])
            print(f"SEMS+ inverters returned for station {selected_id}: {len(inverters)}")

        if failures:
            print(
                "Telemetry failed for station(s): " + ", ".join(failures),
                file=sys.stderr,
            )
            return 1
        return 0
    except Exception as error:
        logger.exception("SEMS+ station discovery failed")
        print(f"SEMS+ station discovery failed: {error}", file=sys.stderr)
        return 1
    finally:
        goodwe_module.requests.get = original_get
        goodwe_module.requests.post = original_post


if __name__ == "__main__":
    raise SystemExit(main())