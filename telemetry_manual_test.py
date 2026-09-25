"""Manually verify live telemetry through the GoodWe SEMS+ web API.

Fill in the configuration values below, then run:

    python telemetry_manual_test.py
"""

import json
import logging
import sys

from GoodWe import GoodWeSEMSPlus


# Set these values before running the script.
SEMS_USERNAME = ""
SEMS_PASSWORD = ""
STATION_ID = ""
SEMS_SERVER = "eu.semsportal.com"


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

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

    print(f"Querying telemetry for station {station_id}...")
    try:
        response = account.stationDataRequest(station_id)
    except Exception as error:
        print(f"Telemetry request failed: {error}", file=sys.stderr)
        return 1

    print(json.dumps(response, indent=2, sort_keys=True))
    inverters = response.get("data", {}).get("inverter", []) if isinstance(response, dict) else []
    if not inverters:
        print("The endpoint returned no device telemetry for this station.", file=sys.stderr)
        return 1

    print(f"Received telemetry for {len(inverters)} device(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())