import unittest
import base64
import hashlib
import json
from unittest.mock import Mock, patch
from GoodWe import GoodWe
from GoodWe import GoodWeSEMSPlus
from GoodWe import NEW_LOGIN_URL
from GoodWe import PowerStation
from GoodWe import Inverter
import logging


class BasicInverterTest(unittest.TestCase):
    inverter = None
    inverterApi = None

    def setUp(self):
        # inverter API data is part of the GetMonitorDetailByPowerstationId API data
        self.inverterApi = {
            "sn": "sn_simple",
            "name": "name_simple",
            "change_num": 0,
            "change_type": 0,
            "relation_sn": None,
            "relation_name": None,
            "status": -1,
        }
        self.inverter = Inverter(self.inverterApi)

    def test_invSerial(self):
        self.assertEqual(self.inverter.serialNumber, "sn_simple")

    def test_invType(self):
        self.assertEqual(self.inverter.type, "name_simple")


class PowerStationTest(unittest.TestCase):
    powerStation = None
    powerStationSingle = None
    powerStationDouble = None
    powerStationApiDataSingle = None
    powerStationApiDataDouble = None

    def setUp(self):
        print("starting the test")
        logging.info("starting the test")

    def test_starting_out(self):
        self.assertEqual(1, 1)

    def test_powerStationId(self):
        stationId = "a73d66f6-aa49-428e-9f93-bdd781f04b7a"
        self.powerStation = PowerStation(id=stationId)
        self.assertEqual(self.powerStation.id, "a73d66f6-aa49-428e-9f93-bdd781f04b7a")
        self.assertEqual(self.powerStation.name, "")
        self.assertEqual(self.powerStation.firstFreeDeviceNum, 0)

    def test_singlePowerStation(self):
        # power station api data is part of the QueryPowerStationByHistory api data
        # this is a single PS
        self.powerStationApiDataSingle = {
            "info": {
                "powerstation_id": "a73d66f6-aa49-428e-9f93-bdd781f04b7e",
                "stationname": "pw_name_1",
                "address": "pw_address_1",
                "status": 1,
            },
            "inverter": [
                {
                    "sn": "inverter_SN1",
                    "name": "inverter_name1",
                    "change_num": 0,
                    "change_type": 0,
                    "relation_sn": None,
                    "relation_name": None,
                    "status": 1,
                }
            ],
        }
        self.powerStationSingle = PowerStation(
            stationData=self.powerStationApiDataSingle
        )
        print("Created power station: '" + str(self.powerStationSingle) + "'")
        logging.info("Created power station: '" + str(self.powerStationSingle) + "'")
        self.assertEqual(
            self.powerStationSingle.id,
            "a73d66f6-aa49-428e-9f93-bdd781f04b7e",
            msg="Single PS ID fail",
        )
        self.assertEqual(
            self.powerStationSingle.name, "pw_name_1", msg="Single PS name fail"
        )
        self.assertEqual(
            self.powerStationSingle.numInverters,
            1,
            msg="Single PS num inv fail: " + str(self.powerStationSingle.numInverters),
        )

    def test_doublePowerStation(self):
        self.powerStationApiDataDouble = {
            "info": {
                "powerstation_id": "a73d66f6-aa49-428e-9f93-bdd781f04b7d",
                "stationname": "pw_name_2",
                "address": "pw_address_2",
                "status": 1,
            },
            "inverter": [
                {
                    "sn": "inverter_SN21",
                    "name": "inverter_name21",
                    "change_num": 0,
                    "change_type": 0,
                    "relation_sn": None,
                    "relation_name": None,
                    "status": 1,
                },
                {
                    "sn": "inverter_SN22",
                    "name": "inverter_name22",
                    "change_num": 0,
                    "change_type": 0,
                    "relation_sn": None,
                    "relation_name": None,
                    "status": 1,
                },
            ],
        }
        self.powerStationDouble = PowerStation(
            stationData=self.powerStationApiDataDouble
        )
        logging.info("Created power station: '" + str(self.powerStationDouble) + "'")
        print("Created power station: '" + str(self.powerStationDouble) + "'")
        self.assertEqual(
            self.powerStationDouble.id,
            "a73d66f6-aa49-428e-9f93-bdd781f04b7d",
            msg="Double PS ID fail",
        )
        self.assertEqual(
            self.powerStationDouble.name, "pw_name_2", msg="Double PS name fail"
        )
        self.assertEqual(
            self.powerStationDouble.numInverters,
            2,
            msg="Double PS num inv fail: " + str(self.powerStationDouble.numInverters),
        )

    # def test_doublePowerStation(self):

    def tearDown(self):
        logging.info("tearing down the house")
        print("tearing down the house")
        self.powerStationSingle = None
        self.powerStationDouble = None
        self.powerStation = None


class GoodWeSemsAuthenticationTest(unittest.TestCase):
    @patch("GoodWe.requests.post")
    def test_token_request_matches_goodwe_dz_login(self, post):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "code": "00000",
            "data": {
                "uid": "user-id",
                "timestamp": 123,
                "token": "sems-token",
                "client": "semsPlusWeb",
                "version": "1",
                "region": "eu",
                "api": "https://eu-gateway.semsportal.com/web/sems",
            },
        }
        post.return_value = response
        account = GoodWeSEMSPlus("eu.semsportal.com", "443", "user@example.com", "password")

        account.tokenRequest()

        post.assert_called_once()
        self.assertEqual(post.call_args.args[0], NEW_LOGIN_URL)
        payload = post.call_args.kwargs["json"]
        expected_password = base64.b64encode(
            hashlib.md5(b"password").hexdigest().encode("utf-8")
        ).decode("utf-8")
        self.assertEqual(payload, {
            "account": "user@example.com",
            "pwd": expected_password,
            "agreement": 1,
            "isChinese": False,
            "isLocal": True,
        })
        self.assertEqual(json.loads(post.call_args.kwargs["headers"]["token"])["client"], "semsPlusWeb")
        self.assertTrue(account.tokenAvailable)
        self.assertEqual(account.token["token"], "sems-token")


class GoodWeFallbackMappingTest(unittest.TestCase):
    def test_station_data_request_v2_accepts_normalized_fallback(self):
        account = GoodWeSEMSPlus("eu.semsportal.com", "443", "user@example.com", "password")
        expected = {"inverter": [{"sn": "54200DSN196R0358"}]}
        account.stationDataRequest = lambda station_id: expected

        self.assertEqual(account.stationDataRequestV2("station-uuid"), expected)

    def test_unknown_sems_status_maps_from_live_output(self):
        account = GoodWeSEMSPlus("eu.semsportal.com", "443", "user@example.com", "password")
        account.getWebInverterDevices = lambda station_id: [{
            "sn": "54200DSN196R0358",
            "name": "GW4200D-NS",
            "deviceType": "INVERTER",
            "status": 5,
        }]
        account.getWebInverterTelemetry = lambda station_id, serial_number, device_type: {
            "output_power": 1497.0,
            "output_current": 6.8,
            "output_voltage": 237.5,
            "tempperature": 34.6,
            "d": {"fac1": 49.98},
            "pv_input_1": "242.8V/3.2A",
        }
        account.getWebInverterTelecounting = lambda station_id, serial_number, device_type: {
            "eday": 3.1,
            "etotal": 25415.0,
        }

        result = account.getWebData("station-uuid")

        self.assertEqual(result["inverter"][0]["status"], 1)
        self.assertEqual(account.INVERTER_STATE[result["inverter"][0]["status"]], "generating")


class GoodWeOpenApiTest(unittest.TestCase):
    @patch("GoodWe.requests.post")
    def test_openapi_methods_use_documented_request_contracts(self, post):
        device_response = Mock()
        device_response.status_code = 200
        device_response.json.return_value = {"code": "00000", "msg": "ok", "data": []}
        telemetry_response = Mock()
        telemetry_response.status_code = 200
        telemetry_response.json.return_value = {
            "code": "00000",
            "msg": "ok",
            "data": {"deviceData": [{"sn": "serial-1", "parameters": {"pvPower": "4500"}}]},
        }
        post.side_effect = [device_response, telemetry_response]
        account = GoodWeSEMSPlus("eu.semsportal.com", "443", "user@example.com", "password")
        account.token = {
            "uid": "user-id",
            "timestamp": 123,
            "token": "sems-session-token",
            "client": "semsPlusWeb",
            "api": "https://eu-gateway.semsportal.com/web/sems",
        }
        account.base_url = account.token["api"]

        device_result = account.openApiDeviceListRequest("station-uuid")
        telemetry_result = account.openApiDeviceTelemetryRequest(["serial-1"], 0)

        self.assertEqual(account.token["token"], "sems-session-token")
        self.assertEqual(device_result["code"], "00000")
        self.assertEqual(telemetry_result["data"]["deviceData"][0]["sn"], "serial-1")
        self.assertEqual(post.call_args_list[0].args[0], "https://eu-gateway.semsportal.com/goodwe/integration/api/v1/base-info/plant/devices")
        self.assertEqual(post.call_args_list[0].kwargs["json"], {"searchType": 1, "searchKey": ["station-uuid"]})
        self.assertEqual(post.call_args_list[1].args[0], "https://eu-gateway.semsportal.com/goodwe/integration/api/v1/realtime/devices")
        self.assertEqual(post.call_args_list[1].kwargs["json"], {"sns": ["serial-1"], "deviceType": 0})
        request_headers = post.call_args_list[1].kwargs["headers"]
        self.assertEqual(request_headers["Authorization"], "Bearer sems-session-token")
        self.assertEqual(json.loads(request_headers["token"])["token"], "sems-session-token")
        self.assertTrue(request_headers["Request-Id"])

    def test_openapi_telemetry_rejects_more_than_100_devices(self):
        account = GoodWeSEMSPlus("eu.semsportal.com", "443", "user@example.com", "password")
        account.openApiBaseUrl = "https://eu-gateway.semsportal.com"
        account.openApiToken = "openapi-token"

        with self.assertRaises(ValueError):
            account.openApiDeviceTelemetryRequest(["sn"] * 101, 0)


def main():
    logging.basicConfig(format='%(asctime)s - %(levelname)-8s - %(filename)-18s - %(message)s', filename="goodwe_test.log",level=logging.DEBUG)
    logging.info("==== starting test run ====")
    unittest.main()
    logging.info("==== finished test run ====")


if __name__ == "__main__":
    main()
