"""Manually verify live telemetry through the GoodWe SEMS+ web API.

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

    print(f"===== Querying Domoticz telemetry for station {station_id}... =====")
    original_get = goodwe_module.requests.get

    def print_response_body(*args, **kwargs):
        response = original_get(*args, **kwargs)
        try:
            response_body = response.json()
        except Exception:
            response_body = response.text
        print(f"\n===== GET {response.url} (HTTP {response.status_code}) =====")
        print(json.dumps(response_body, indent=2, sort_keys=True, default=str))
        return response

    goodwe_module.requests.get = print_response_body
    try:
        station_data = account.stationDataRequestV2(station_id)
    except Exception as error:
        logger.exception("SEMS+ Domoticz telemetry request failed")
        print(f"SEMS+ telemetry request failed: {error}", file=sys.stderr)
        return 1
    finally:
        goodwe_module.requests.get = original_get

    if not isinstance(station_data, dict):
        print("SEMS+ returned no station telemetry data.", file=sys.stderr)
        return 1

    print("\n===== Normalized station data passed to Domoticz =====")
    print(json.dumps(station_data, indent=2, sort_keys=True, default=str))
    inverters = station_data.get("inverter", [])
    print(f"\nSEMS+ devices returned: {len(inverters)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())