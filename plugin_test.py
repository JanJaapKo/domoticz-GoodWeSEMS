import unittest
from unittest.mock import Mock, patch
from GoodWe import GoodWe
from GoodWe import GoodWeSEMSPlus
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


class GoodWeOpenApiTest(unittest.TestCase):
    station_id = "plant-123"
    serial_number = "8033KETF11AW6230"

    def setUp(self):
        self.account = GoodWeSEMSPlus(
            "eu.semsportal.com",
            "443",
            "user@example.com",
            "password",
            "client-id",
            "client-secret",
            "eu-gateway.semsportal.com",
        )
        self.account.token = {"access_token": "test-access-token"}

    def _response(self, data):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"code": "00000", "data": data}
        return response

    @patch("GoodWe.requests.post")
    def test_station_data_uses_documented_telemetry_endpoints(self, post):
        post.side_effect = [
            self._response([
                {
                    "plantId": self.station_id,
                    "deviceData": [{
                        "deviceSn": self.serial_number,
                        "deviceName": "Inverter",
                        "deviceType": 0,
                    }],
                }
            ]),
            self._response({
                "deviceData": [{
                    "sn": self.serial_number,
                    "parameters": {
                        "deviceStatus": 1,
                        "pvPower": 4500.5,
                        "acVoltage1": 220.3,
                        "acCurrent1": 18.5,
                        "acFrequency1": 50,
                        "innerTemperature": 42.3,
                        "dailyGeneration": 32.5,
                        "totalGeneration": 15680.75,
                        "dcVoltage1": 35.2,
                        "dcCurrent1": 12.3,
                    },
                }]
            }),
        ]

        result = self.account.stationDataRequest(self.station_id)

        self.assertEqual(
            [call.args[0] for call in post.call_args_list],
            [
                "https://eu-gateway.semsportal.com/goodwe/integration/api/v1/base-info/plant/devices",
                "https://eu-gateway.semsportal.com/goodwe/integration/api/v1/realtime/devices",
            ],
        )
        self.assertEqual(post.call_args_list[0].kwargs["json"], {
            "searchType": 1,
            "searchKey": [self.station_id],
        })
        telemetry_call = post.call_args_list[1]
        self.assertEqual(telemetry_call.kwargs["json"], {
            "sns": [self.serial_number],
            "deviceType": 0,
        })
        self.assertEqual(telemetry_call.kwargs["headers"]["Authorization"], "Bearer test-access-token")
        self.assertTrue(telemetry_call.kwargs["headers"]["Request-Id"])
        inverter = result["data"]["inverter"][0]
        self.assertEqual(inverter["output_power"], 4500.5)
        self.assertEqual(inverter["d"]["fac1"], 50)
        self.assertEqual(inverter["pv_input_1"], "35.2V/12.3A")
        self.assertEqual(inverter["etotal"], 15680.75)

    @patch("GoodWe.requests.post")
    def test_token_request_uses_client_credentials(self, post):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"access_token": "access-token", "expires_in": 3600}
        post.return_value = response

        self.account.tokenRequest()

        post.assert_called_once_with(
            "https://eu-gateway.semsportal.com/goodwe/goodwe-authorization-server/oauth2/token",
            auth=("client-id", "client-secret"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "client_credentials"},
            timeout=30,
        )
        self.assertTrue(self.account.tokenAvailable)
        self.assertEqual(self.account.token["access_token"], "access-token")


def main():
    logging.basicConfig(format='%(asctime)s - %(levelname)-8s - %(filename)-18s - %(message)s', filename="goodwe_test.log",level=logging.DEBUG)
    logging.info("==== starting test run ====")
    unittest.main()
    logging.info("==== finished test run ====")


if __name__ == "__main__":
    main()
