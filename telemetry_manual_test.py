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

    print("Requesting SEMS+ access token...")
    account.tokenRequest()
    if not account.tokenAvailable:
        print("Token request failed; check the SEMS+ server and account credentials.", file=sys.stderr)
        return 1

    print(f"Querying current SEMS+ data for station {station_id}...")
    try:
        sems_response = account.stationDataRequest(station_id)
    except Exception as error:
        sems_response = None
        print(f"SEMS+ data request failed: {error}", file=sys.stderr)

    print("\n--- Existing SEMS+ result ---")
    print(json.dumps(sems_response, indent=2, sort_keys=True, default=str))
    sems_inverters = sems_response.get("data", {}).get("inverter", []) if isinstance(sems_response, dict) else []
    print(f"SEMS+ devices returned: {len(sems_inverters)}")

    try:
        print("\nUsing the SEMS+ token for OpenAPI endpoint comparison...")
        print("Querying OpenAPI device list...")
        device_list_response = account.openApiDeviceListRequest(station_id)
        print("\n--- OpenAPI device list result ---")
        print(json.dumps(device_list_response, indent=2, sort_keys=True, default=str))

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

        telemetry_count = 0
        for device_type, serial_numbers in devices_by_type.items():
            for offset in range(0, len(serial_numbers), 100):
                batch = serial_numbers[offset:offset + 100]
                telemetry_response = account.openApiDeviceTelemetryRequest(batch, device_type)
                print(f"\n--- OpenAPI telemetry: deviceType={device_type}, serials={batch} ---")
                print(json.dumps(telemetry_response, indent=2, sort_keys=True, default=str))
                telemetry_data = telemetry_response.get("data", {})
                if isinstance(telemetry_data, dict):
                    telemetry_count += len(telemetry_data.get("deviceData", []))
    except Exception as error:
        print(f"OpenAPI comparison request failed: {error}", file=sys.stderr)
        return 1

    if not telemetry_count:
        print("The OpenAPI telemetry endpoint returned no device data.", file=sys.stderr)
        return 1

    print(f"Received OpenAPI telemetry for {telemetry_count} device(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())