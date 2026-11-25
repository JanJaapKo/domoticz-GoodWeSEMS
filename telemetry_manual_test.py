"""Manually verify SEMS+ telemetry and Home Assistant battery endpoints.

Copy `.env.example` to `.env`, fill in your SEMS+ credentials, then run:

    python telemetry_manual_test.py

The output contains station and device identifiers. Mask them before sharing.
"""

import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote, urlencode

import GoodWe as goodwe_module
from GoodWe import GoodWeSEMSPlus

logger = None

HA_STATISTICS_ITEMS = [
    "proConsumStats",
    "proGridStats",
    "proPurchaseStats",
    "proSelfConsumStats",
    "proDischarStats",
    "proCharStats",
    "proSystemTotalStats",
]


def load_env_file(path):
    if not path.is_file():
        return

    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        entry = line.strip()
        if not entry or entry.startswith("#"):
            continue
        if entry.startswith("export "):
            entry = entry[len("export "):].strip()

        name, separator, value = entry.partition("=")
        name = name.strip()
        valid_name = bool(name) and (name[0].isalpha() or name[0] == "_")
        valid_name = valid_name and all(
            character.isalnum() or character == "_" for character in name
        )
        if not separator or not valid_name:
            raise ValueError(f"Invalid .env entry on line {line_number}")

        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        os.environ.setdefault(name, value)


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


def request_web_endpoint(account, method, url_part, payload=None):
    """Request a read-only SEMS+ Web endpoint using the account's session."""
    method = method.upper()
    if method not in ("GET", "POST"):
        raise ValueError("Only GET and POST are supported by the telemetry tester")

    headers = account.apiRequestHeadersV2()
    if isinstance(account.token, dict) and account.token.get("client") == "semsPlusWeb":
        signature = account._generate_signature(account.token)
        if signature:
            headers["X-Signature"] = signature

    request = getattr(goodwe_module.requests, method.lower())
    request_kwargs = {"headers": headers, "timeout": 10}
    if payload is not None:
        request_kwargs["json"] = payload
    response = request(account.base_url.rstrip("/") + url_part, **request_kwargs)
    response.raise_for_status()
    try:
        response_body = response.json()
    except ValueError as error:
        raise ValueError(f"{method} {url_part} did not return valid JSON") from error

    if isinstance(response_body, dict) and "code" in response_body:
        if str(response_body["code"]) not in ("0", "00000"):
            raise ValueError(
                f"{method} {url_part} returned API code "
                f"{response_body['code']}: "
                f"{response_body.get('msg', response_body.get('description', ''))}"
            )
    return response_body


def get_response_data(response_body):
    """Return the data payload from an API envelope when one is present."""
    if isinstance(response_body, dict) and "data" in response_body:
        return response_body["data"]
    return response_body


def probe_ha_battery_endpoints(account, station_id, station_data):
    """Query HA's additional read-only battery endpoints without repeating
    station discovery or inverter telemetry already requested above.
    """
    failures = []

    def request_optional(label, method, url_part, payload=None):
        print(f"\n===== Querying HA {label} =====")
        try:
            return request_web_endpoint(account, method, url_part, payload)
        except (goodwe_module.requests.exceptions.RequestException, ValueError) as error:
            print(f"HA {label} request failed: {error}", file=sys.stderr)
            failures.append(label)
            return None

    station_query = urlencode({"stationId": station_id})
    request_optional(
        "station flow",
        "GET",
        f"/sems-plant/api/stations/flow?{station_query}",
    )

    now = datetime.now().astimezone()
    request_optional(
        "station statistics (current day)",
        "POST",
        "/sems-plant/api/stations/statistics",
        {
            "stationId": station_id,
            "isReport": False,
            "items": HA_STATISTICS_ITEMS,
            "dimension": "day",
            "startTime": now.strftime("%Y-%m-%d %H:%M:%S"),
            "endTime": (now + timedelta(days=1) - timedelta(seconds=1)).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        },
    )

    # station_data already includes the all-status result and inverter
    # telemetry/counters. Reuse its inverter identities rather than requesting
    # those endpoints a second time.
    storage_inverters = {}
    for inverter in station_data.get("inverter", []):
        if not isinstance(inverter, dict):
            continue
        serial_number = inverter.get("sn")
        is_storage = (
            inverter.get("subtype") == "store"
            or inverter.get("deviceType") == "ENERGY_STORAGE_INTEGRATED_CABINET"
        )
        if isinstance(serial_number, str) and serial_number and is_storage:
            storage_inverters.setdefault(serial_number, inverter)

    queried_battery_serials = set()
    for serial_number in storage_inverters:
        related_path = (
            f"/sems-plant/api/equipments/{quote(serial_number, safe='')}/relatedDevices?"
            + urlencode({
                "sn": serial_number,
                "deviceType": "ENERGY_STORAGE_INTEGRATED_CABINET",
                "pwId": station_id,
            })
        )
        related_response = request_optional(
            f"related storage devices for inverter {serial_number}",
            "GET",
            related_path,
        )
        if related_response is None:
            continue

        related_devices = get_response_data(related_response)
        if isinstance(related_devices, dict):
            related_devices = related_devices.get("dataList")
        if not isinstance(related_devices, list):
            print(
                f"HA related-device response for inverter {serial_number} "
                "did not contain a device list.",
                file=sys.stderr,
            )
            failures.append(f"related storage devices for inverter {serial_number}")
            continue

        has_connected_battery_slot = False
        for related_device in related_devices:
            if not isinstance(related_device, dict):
                continue

            if (
                related_device.get("translateCode") is not None
                and related_device.get("isConnected") is not False
            ):
                has_connected_battery_slot = True
                request_optional(
                    f"battery functions for inverter {serial_number}, "
                    f"slot {related_device.get('no', 0)}",
                    "POST",
                    "/sems-remote/api/v2/address/remote/getDeviceFunctionTabMenus",
                    {
                        "batIndex": str(related_device.get("no", 0)),
                        "menuCode": 1,
                        "module": "GENERAL_FUNCTIONS",
                        "sn": serial_number,
                    },
                )

            device_type = related_device.get("type") or related_device.get("deviceType")
            battery_serial = related_device.get("sn")
            if (
                device_type != "BAT_SYS"
                or not isinstance(battery_serial, str)
                or not battery_serial
                or battery_serial in queried_battery_serials
            ):
                continue

            queried_battery_serials.add(battery_serial)
            battery_query = urlencode(
                {"deviceType": "BAT_SYS", "pwId": station_id}
            )
            request_optional(
                f"BAT_SYS telemetry for battery {battery_serial}",
                "GET",
                f"/sems-plant/api/equipments/"
                f"{quote(battery_serial, safe='')}/telemetry?{battery_query}",
            )

        if has_connected_battery_slot:
            request_optional(
                f"immediate-charging state for inverter {serial_number}",
                "POST",
                "/sems-remote/api/v1/address/remote/get-cache-device-function-parameters",
                {
                    "sn": serial_number,
                    "addresses": ["47545", "47545", "47546", "47603"],
                    "addrFuncMap": {
                        "47545": "2013217017330515970",
                        "47546": "1991791639537946635",
                        "47603": "1991791639537946636",
                    },
                },
            )

    if not storage_inverters:
        print(
            "No storage-capable inverter was identified in the normalized "
            "station data; related battery endpoints were skipped."
        )
    return failures


def main():
    load_env_file(Path(__file__).with_name(".env"))

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

    username = os.environ.get("SEMS_USERNAME", "").strip()
    password = os.environ.get("SEMS_PASSWORD", "").strip()
    station_id = os.environ.get("STATION_ID", "").strip()
    sems_server = os.environ.get("SEMS_SERVER", "eu.semsportal.com").strip()
    if not sems_server:
        sems_server = "eu.semsportal.com"
    missing = [
        name
        for name, value in (
            ("SEMS_USERNAME", username),
            ("SEMS_PASSWORD", password),
        )
        if not value
    ]
    if missing:
        print(
            "Set these values in .env before running: " + ", ".join(missing),
            file=sys.stderr,
        )
        return 2

    account = GoodWeSEMSPlus(
        sems_server,
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
        endpoint_failures = []
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
            endpoint_failures.extend(
                probe_ha_battery_endpoints(account, selected_id, station_data)
            )

        if failures:
            print(
                "Telemetry failed for station(s): " + ", ".join(failures),
                file=sys.stderr,
            )
            return 1
        if endpoint_failures:
            print(
                "One or more optional Home Assistant endpoint probes failed: "
                + ", ".join(endpoint_failures),
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