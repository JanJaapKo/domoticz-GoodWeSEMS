"""Manually verify live telemetry through the GoodWe SEMS+ web API.

Fill in the configuration values below, then run:

    python telemetry_manual_test.py
"""

import json
import logging
import sys, os

from GoodWe import GoodWeSEMSPlus

# Set these values before running the script.
SEMS_USERNAME = ""
SEMS_PASSWORD = ""
STATION_ID = ""
SEMS_SERVER = "eu.semsportal.com"
logger = None

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
            ("STATION_ID", station_id),
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

    print(f"===== Querying telemetry for station {station_id}... =====")
    try:
        sems_response = account.stationDataRequest(station_id)
    except Exception as error:
        sems_response = None
        logger.exception("SEMS+ telemetry request failed")
        print(f"SEMS+ telemetry request failed: {error}", file=sys.stderr)

    print("\n===== SEMS+ result =====")
    print(json.dumps(sems_response, indent=2, sort_keys=True, default=str))
    sems_data = sems_response.get("data", sems_response) if isinstance(sems_response, dict) else {}
    sems_inverters = sems_data.get("inverter", []) if isinstance(sems_data, dict) else []
    print(f"SEMS+ devices returned: {len(sems_inverters)}")

    telemetry_count = 0
    try:
        logger.info("OPENAPI START Query Device List Under Station: stationId=%s", station_id)
        print(f"\n===== OPENAPI START Query Device List Under Station: {station_id} =====")
        device_list_response = account.openApiDeviceListRequest(station_id)
        device_list_json = json.dumps(device_list_response, indent=2, sort_keys=True, default=str)
        logger.info("OPENAPI RESULT Query Device List Under Station:\n%s", device_list_json)
        print("===== OPENAPI RESULT Query Device List Under Station =====")
        print(device_list_json)

        response_data = device_list_response.get("data", [])
        plants = response_data if isinstance(response_data, list) else []
        devices_by_type = {}
        for plant in plants:
            if not isinstance(plant, dict) or plant.get("plantId") != station_id:
                continue
            for device in plant.get("deviceData", []):
                if not isinstance(device, dict):
                    continue
                serial_number = device.get("deviceSn")
                device_type = device.get("deviceType")
                if isinstance(serial_number, str) and isinstance(device_type, int):
                    devices_by_type.setdefault(device_type, []).append(serial_number)

        for device_type, serial_numbers in devices_by_type.items():
            for offset in range(0, len(serial_numbers), 100):
                batch = serial_numbers[offset:offset + 100]
                logger.info(
                    "OPENAPI START Query Device Real-time Telemetry Data: deviceType=%s, sns=%s",
                    device_type,
                    batch,
                )
                print(f"\n===== OPENAPI START Query Device Real-time Telemetry Data: deviceType={device_type}, sns={batch} =====")
                telemetry_response = account.openApiDeviceTelemetryRequest(batch, device_type)
                telemetry_json = json.dumps(telemetry_response, indent=2, sort_keys=True, default=str)
                logger.info(
                    "OPENAPI RESULT Query Device Real-time Telemetry Data: deviceType=%s\n%s",
                    device_type,
                    telemetry_json,
                )
                print(f"===== OPENAPI RESULT Query Device Real-time Telemetry Data: deviceType={device_type} =====")
                print(telemetry_json)
                telemetry_data = telemetry_response.get("data", {})
                if isinstance(telemetry_data, dict):
                    telemetry_count += len(telemetry_data.get("deviceData", []))
    except Exception as error:
        logger.exception("OPENAPI request failed")
        print(f"OpenAPI request failed: {error}", file=sys.stderr)
        return 1

    if not telemetry_count:
        logger.warning("OPENAPI RESULT: no device telemetry returned for station %s", station_id)
        print("The OpenAPI telemetry endpoint returned no device data.", file=sys.stderr)
        return 1

    logger.info("OPENAPI RESULT: telemetry returned for %s device(s)", telemetry_count)
    print(f"\n===== OPENAPI telemetry returned for {telemetry_count} device(s). =====")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())