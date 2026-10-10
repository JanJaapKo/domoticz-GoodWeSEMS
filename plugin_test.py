import unittest
import base64
import hashlib
import json
import GoodWe as goodwe_module
from unittest.mock import Mock, patch
from GoodWe import GoodWe
from GoodWe import GoodWeSEMSPlus
from GoodWe import NEW_LOGIN_URL
from GoodWe import PowerStation
from GoodWe import Inverter
import exceptions
import logging
import manual_test


def make_response(payload, url="https://example.test/api"):
    response = Mock()
    response.url = url
    response.status_code = 200
    response.text = json.dumps(payload)
    response.json.return_value = payload
    return response


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

    def test_invWithoutNameFallsBackToSerialNumber(self):
        inverter = Inverter({"sn": "sn_no_name"})
        self.assertEqual(inverter.serialNumber, "sn_no_name")
        self.assertEqual(inverter.type, "sn_no_name")


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

    def test_partialStationInfoDoesNotCrash(self):
        station_data = {
            "info": {"powerstation_id": "station-without-name"},
            "inverter": [{"sn": "inv_without_name"}],
        }
        station = PowerStation(stationData=station_data)
        self.assertEqual(station.id, "station-without-name")
        self.assertEqual(station.name, "station-without-name")
        self.assertEqual(station.numInverters, 1)
        self.assertEqual(station.inverters["inv_without_name"].type, "inv_without_name")

    # def test_doublePowerStation(self):

    def tearDown(self):
        logging.info("tearing down the house")
        print("tearing down the house")
        self.powerStationSingle = None
        self.powerStationDouble = None
        self.powerStation = None


class PluginBehaviorTest(unittest.TestCase):
    def setUp(self):
        self.plugin_module = manual_test.load_plugin_module()
        manual_test.setup_plugin_environment(self.plugin_module)

    def _start_plugin(self):
        plugin = self.plugin_module._plugin
        plugin.checkVersion = Mock(return_value=True)
        plugin.startDeviceUpdateV2 = Mock()
        created_handlers = []

        class NullFileHandler(self.plugin_module.logging.NullHandler):
            def __init__(self, filename, *args, **kwargs):
                super().__init__()
                created_handlers.append(self)

        root_logger = self.plugin_module.logging.getLogger()
        original_level = root_logger.level
        try:
            with patch.object(self.plugin_module.logging, "FileHandler", NullFileHandler):
                plugin.onStart()
        finally:
            for handler in created_handlers:
                root_logger.removeHandler(handler)
                handler.close()
            root_logger.setLevel(original_level)
        return plugin

    def test_update_device_only_writes_changed_values(self):
        manual_test.test_update_device(self.plugin_module)

    def test_calculate_new_energy_from_elapsed_time(self):
        manual_test.test_calculate_new_energy(self.plugin_module)

    def test_update_devices_protects_existing_energy_counter(self):
        manual_test.test_update_devices_skips_zero_counter_reset(self.plugin_module)

    def test_create_devices_adds_expected_units(self):
        manual_test.test_create_devices(self.plugin_module)

    def test_station_discovery_persists_selected_id(self):
        manual_test.test_power_station_discovery_and_persistence(self.plugin_module)

    def test_missing_station_id_skips_telemetry(self):
        manual_test.test_station_discovery_failure_skips_telemetry(self.plugin_module)

    def test_version_check_persists_upgrade(self):
        manual_test.test_check_version(self.plugin_module)

    def test_establish_token_refreshes_account_state(self):
        plugin = self.plugin_module._plugin
        account = Mock(tokenAvailable=False, powerStationList={1: "stale"}, powerStationIndex=2)
        account.tokenRequest.side_effect = lambda: setattr(account, "tokenAvailable", True)
        plugin.goodWeAccount = account
        plugin.devicesUpdated = True

        self.assertTrue(plugin.establishToken())

        account.tokenRequest.assert_called_once_with()
        self.assertEqual(account.powerStationList, {})
        self.assertEqual(account.powerStationIndex, 0)
        self.assertFalse(plugin.devicesUpdated)

    def test_establish_token_keeps_an_existing_session(self):
        plugin = self.plugin_module._plugin
        account = Mock(tokenAvailable=True)
        plugin.goodWeAccount = account

        self.assertTrue(plugin.establishToken())

        account.tokenRequest.assert_not_called()

    def test_semsplus_device_update_does_not_force_periodic_login(self):
        plugin = self.plugin_module._plugin
        self.plugin_module.Parameters["Mode4"] = "No"
        plugin.establishToken = Mock(return_value=True)
        plugin.getPowerStationId = Mock(return_value="station-uuid")
        plugin.getDeviceData = Mock(return_value={"inverter": []})
        plugin.goodWeAccount = GoodWeSEMSPlus("eu.semsportal.com", "443", "user@example.com", "password")
        plugin.updateDevices = Mock()

        plugin.startDeviceUpdateV2()

        plugin.establishToken.assert_called_once_with()
        plugin.getDeviceData.assert_called_once_with("station-uuid")

    def test_establish_token_handles_known_api_errors(self):
        plugin = self.plugin_module._plugin
        account = Mock(tokenAvailable=False)
        account.tokenRequest.side_effect = exceptions.FailureWithMessage("invalid")
        plugin.goodWeAccount = account

        self.assertFalse(plugin.establishToken())

    def test_get_device_data_requires_token_and_handles_api_errors(self):
        plugin = self.plugin_module._plugin
        plugin.goodWeAccount = Mock(tokenAvailable=False)
        self.assertIsNone(plugin.getDeviceData("station-uuid"))

        plugin.goodWeAccount.tokenAvailable = True
        plugin.goodWeAccount.stationDataRequestV2.side_effect = exceptions.TooManyRetries()
        self.assertIsNone(plugin.getDeviceData("station-uuid"))

    def test_config_helpers_read_write_and_reject_unsupported_values(self):
        self.assertEqual(self.plugin_module.getConfigItem("missing", "fallback"), "fallback")
        self.plugin_module.setConfigItem("station", "station-uuid")
        self.assertEqual(self.plugin_module.getConfigItem("station"), "station-uuid")

        self.plugin_module.setConfigItem("unsupported", object())
        self.assertEqual(self.plugin_module.getConfigItem("unsupported"), {})

    def test_legacy_heartbeat_schedules_at_configured_interval(self):
        plugin = self.plugin_module._plugin
        plugin.enabled = True
        plugin.runAgain = 2
        self.plugin_module.Parameters["Mode4"] = "No"
        self.plugin_module.Parameters["Mode2"] = "3"
        plugin.httpConn = None
        plugin.startDeviceUpdateV2 = Mock()

        plugin.onHeartbeat()
        self.assertEqual(plugin.runAgain, 1)
        plugin.startDeviceUpdateV2.assert_not_called()

        plugin.onHeartbeat()
        plugin.startDeviceUpdateV2.assert_called_once_with()
        self.assertEqual(plugin.runAgain, 3)

    def test_disconnect_clears_connection_and_stop_disconnects_active_connection(self):
        plugin = self.plugin_module._plugin
        connection = Mock(Address="eu.semsportal.com", Port="443")
        plugin.httpConn = connection

        plugin.onDisconnect(connection)
        self.assertIsNone(plugin.httpConn)

        plugin.httpConn = connection
        plugin.onStop()
        connection.Disconnect.assert_called_once_with()

    def test_upgrade_refuses_existing_devices_below_framework_version(self):
        self.plugin_module.Devices = {"existing": object()}

        self.assertFalse(self.plugin_module._plugin.updateToEx())
        self.assertEqual(self.plugin_module.getConfigItem("plugin version"), "4.0.0")

    def test_on_start_initializes_semsplus_client_and_update_interval(self):
        self.plugin_module.Parameters["Mode4"] = "Yes"
        self.plugin_module.Parameters["Mode6"] = "Debug"
        self.plugin_module.Parameters["Mode2"] = "6"

        plugin = self._start_plugin()

        self.assertIsInstance(plugin.goodWeAccount, GoodWeSEMSPlus)
        self.assertEqual(plugin.runAgain, 6)
        plugin.startDeviceUpdateV2.assert_called_once_with()

    def test_on_start_initializes_legacy_client_when_semsplus_is_disabled(self):
        self.plugin_module.Parameters["Mode4"] = "No"

        plugin = self._start_plugin()

        self.assertIsInstance(plugin.goodWeAccount, GoodWe)
        plugin.startDeviceUpdateV2.assert_called_once_with()

    def test_update_devices_maps_generating_inverter_and_all_pv_strings(self):
        plugin = self.plugin_module._plugin
        station = PowerStation(stationData={
            "info": {"powerstation_id": "station-uuid"},
            "inverter": [{"sn": "sn_generating", "name": "inverter"}],
        })
        account = Mock()
        account.powerStationList = {1: station}
        account.INVERTER_STATE = GoodWe.INVERTER_STATE
        plugin.goodWeAccount = account
        self.plugin_module.Devices = {}
        plugin.createDevices("sn_generating")

        plugin.updateDevices({"inverter": [{
            "sn": "sn_generating",
            "fault_message": "",
            "status": 1,
            "tempperature": 36.2,
            "d": {"fac1": 50.0},
            "output_current": 6.0,
            "output_voltage": 240.0,
            "output_power": 1440.0,
            "etotal": 12.5,
            "pv_input_1": "250V/3A",
            "pv_input_2": "251V/4A",
            "pv_input_3": "252V/5A",
            "pv_input_4": "253V/6A",
            "battery": "",
            "bms_status": "",
            "battery_power": "",
        }]})

        units = self.plugin_module.Devices["sn_generating"].Units
        self.assertEqual(units[plugin.inverterStateUnit].sValue, "30")
        self.assertEqual(units[plugin.inverterTemperatureUnit].sValue, "36.2")
        self.assertEqual(units[plugin.outputFreq1Unit].sValue, "50.0")
        self.assertEqual(units[plugin.outputPowerUnit].sValue, "1440.0;12500.0")
        self.assertEqual(units[plugin.inputVoltage1Unit].sValue, "250V")
        self.assertEqual(units[plugin.inputAmps1Unit].sValue, "3A")
        self.assertEqual(units[plugin.inputVoltage2Unit].sValue, "251V")
        self.assertEqual(units[plugin.inputVoltage3Unit].sValue, "252V")
        self.assertEqual(units[plugin.inputVoltage4Unit].sValue, "253V")
        self.assertNotIn(plugin.outputVoltageBUnit, units)
        self.assertNotIn(plugin.outputVoltageCUnit, units)
        self.assertNotIn(plugin.outputCurrentBUnit, units)
        self.assertNotIn(plugin.outputCurrentCUnit, units)

    def test_update_devices_creates_only_reported_ac_phases(self):
        plugin = self.plugin_module._plugin
        station = PowerStation(stationData={
            "info": {"powerstation_id": "station-uuid"},
            "inverter": [{"sn": "sn_three_phase", "name": "inverter"}],
        })
        account = Mock()
        account.powerStationList = {1: station}
        account.INVERTER_STATE = GoodWe.INVERTER_STATE
        plugin.goodWeAccount = account
        self.plugin_module.Devices = {}

        plugin.updateDevices({"inverter": [{
            "sn": "sn_three_phase",
            "fault_message": "",
            "status": 1,
            "tempperature": 36.2,
            "d": {"fac1": 50.0},
            "output_current": 8.1,
            "output_current_b": 8.7,
            "output_current_c": 8.3,
            "output_voltage": 230.0,
            "output_voltage_b": 231.0,
            "output_voltage_c": 232.0,
            "output_power": 1440.0,
            "etotal": 12.5,
            "pv_input_1": "250V/3A",
            "battery": "",
            "bms_status": "",
            "battery_power": "",
        }]})

        units = self.plugin_module.Devices["sn_three_phase"].Units
        self.assertEqual(units[plugin.outputCurrentUnit].sValue, "8.1")
        self.assertEqual(units[plugin.outputVoltageUnit].sValue, "230.0")
        self.assertEqual(units[plugin.outputCurrentBUnit].sValue, "8.7")
        self.assertEqual(units[plugin.outputVoltageBUnit].sValue, "231.0")
        self.assertEqual(units[plugin.outputCurrentCUnit].sValue, "8.3")
        self.assertEqual(units[plugin.outputVoltageCUnit].sValue, "232.0")


class GoodWeExceptionsTest(unittest.TestCase):
    def test_exception_hierarchy_preserves_messages(self):
        cases = (
            (exceptions.GoodweException, (), "Error message not defined"),
            (exceptions.GoodweException, ("custom error",), "custom error"),
            (exceptions.TooManyRetries, (), "Failed to call GoodWe API (too many retries)"),
            (exceptions.FailureWithMessage, ("invalid",), "Failed to call GoodWe API (return message = invalid)"),
            (exceptions.FailureWithoutMessage, (), "Failed to call GoodWe API (no return message )"),
            (exceptions.FailureWithErrorCode, (403,), "Failed to call GoodWe API (return code = 403)"),
            (exceptions.FailureWithoutErrorCode, (), "Failed to call GoodWe API (no return code )"),
        )

        for exception_type, args, expected_message in cases:
            with self.subTest(exception=exception_type.__name__):
                error = exception_type(*args)
                self.assertIsInstance(error, exceptions.GoodweException)
                self.assertEqual(str(error), expected_message)


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

    @patch("GoodWe.requests.post")
    def test_semsplus_station_data_request_skips_legacy_monitor_route(self, post):
        account = GoodWeSEMSPlus("eu.semsportal.com", "443", "user@example.com", "password")
        expected = {"inverter": [{"sn": "serial-1"}]}
        account.getWebData = Mock(return_value=expected)

        result = account.stationDataRequest("station-uuid")

        self.assertIs(result, expected)
        account.getWebData.assert_called_once_with("station-uuid")
        post.assert_not_called()

    @patch("GoodWe.requests.post")
    def test_legacy_station_data_request_still_uses_monitor_route(self, post):
        response = Mock()
        response.url = "https://eu.semsportal.com/api/v2/PowerStation/GetMonitorDetailByPowerstationId"
        response.status_code = 200
        response.text = "{}"
        response.json.return_value = {}
        post.return_value = response
        account = GoodWe("eu.semsportal.com", "443", "user@example.com", "password")

        account.stationDataRequest("station-uuid")

        post.assert_called_once()
        self.assertEqual(
            post.call_args.args[0],
            "https://eu.semsportal.com/api/PowerStation/GetMonitorDetailByPowerstationId",
        )

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

    def test_empty_telemetry_and_counters_return_plugin_safe_station_data(self):
        account = GoodWeSEMSPlus("eu.semsportal.com", "443", "user@example.com", "password")
        account.getWebInverterDevices = lambda station_id: [{
            "sn": "54200DSN196R0358",
            "name": "GW4200D-NS",
            "deviceType": "INVERTER",
            "status": 5,
        }]
        account.getWebInverterTelemetry = lambda station_id, serial_number, device_type: {}
        account.getWebInverterTelecounting = lambda station_id, serial_number, device_type: {}

        result = account.getWebData("station-uuid")
        station = PowerStation(stationData=result)
        inverter = result["inverter"][0]

        self.assertEqual(result["info"]["powerstation_id"], "station-uuid")
        self.assertEqual(station.id, "station-uuid")
        self.assertEqual(inverter["status"], 0)
        self.assertEqual(inverter["output_current"], 0)
        self.assertEqual(inverter["output_voltage"], 0)
        self.assertEqual(inverter["output_power"], 0)
        self.assertEqual(inverter["etotal"], 0)
        self.assertEqual(inverter["pv_input_1"], "0V/0A")
        self.assertIn("fac1", inverter["d"])


class GoodWeLegacyApiTest(unittest.TestCase):
    def test_legacy_token_request_uses_component_api_url(self):
        response = make_response({
            "code": 0,
            "components": {"api": "https://regional.semsportal.com/api"},
            "data": {"token": "legacy-token"},
        })
        account = GoodWe("eu.semsportal.com", "443", "user@example.com", "password")

        with patch("GoodWe.requests.post", return_value=response) as post:
            result = account.tokenRequest()

        self.assertEqual(result, 200)
        self.assertTrue(account.tokenAvailable)
        self.assertEqual(account.token, {"token": "legacy-token"})
        self.assertEqual(account.base_url, "https://regional.semsportal.com/api/v2")
        self.assertEqual(post.call_args.kwargs["data"], {
            "account": "user@example.com",
            "pwd": "password",
        })

    def test_legacy_token_request_handles_missing_api_and_transport_failure(self):
        response = make_response({"code": 0, "data": {"token": "token"}})
        account = GoodWe("eu.semsportal.com", "443", "user@example.com", "password")
        with patch("GoodWe.requests.post", return_value=response):
            self.assertIsNone(account.tokenRequest())
        self.assertFalse(account.tokenAvailable)

    def test_legacy_token_request_rejects_invalid_credentials(self):
        response = make_response({"code": 100005})
        account = GoodWe("eu.semsportal.com", "443", "user@example.com", "wrong-password")

        with patch("GoodWe.requests.post", return_value=response):
            with self.assertRaisesRegex(exceptions.GoodweException, "invalid password or username"):
                account.tokenRequest()

        with patch("GoodWe.requests.post", side_effect=goodwe_module.requests.exceptions.Timeout("offline")):
            self.assertIsNone(account.tokenRequest())
        self.assertFalse(account.tokenAvailable)

    def test_legacy_power_station_list_uses_v3_endpoint_and_rejects_http_error(self):
        payload = {"code": 0, "data": [{"id": "station-1"}]}
        response = make_response(payload)
        account = GoodWe("eu.semsportal.com", "443", "user@example.com", "password")
        with patch("GoodWe.requests.post", return_value=response) as post:
            self.assertEqual(account.powerStationListRequest(), payload)

        self.assertEqual(
            post.call_args.args[0],
            "https://eu.semsportal.com/api/v3/PowerStation/GetPowerStationList",
        )
        self.assertEqual(post.call_args.kwargs["json"], {})

        response.raise_for_status.side_effect = goodwe_module.requests.exceptions.HTTPError("bad response")
        with patch("GoodWe.requests.post", return_value=response):
            with self.assertRaises(goodwe_module.requests.exceptions.HTTPError):
                account.powerStationListRequest()

    def test_station_data_request_v2_accepts_legacy_response_and_retries_expired_token(self):
        station_data = {"inverter": [{"sn": "serial-1"}]}
        account = GoodWe("eu.semsportal.com", "443", "user@example.com", "password")
        account.stationDataRequest = Mock(return_value={"code": 0, "data": station_data})
        self.assertEqual(account.stationDataRequestV2("station-uuid"), station_data)

        account.stationDataRequest = Mock(side_effect=[
            {"code": 100001, "data": None},
            {"code": 0, "data": station_data},
        ])
        account.tokenRequest = Mock()
        with patch("GoodWe.time.sleep") as sleep:
            self.assertEqual(account.stationDataRequestV2("station-uuid"), station_data)
        account.tokenRequest.assert_called_once_with()
        sleep.assert_called_once_with(1)

    def test_station_data_request_v2_retries_transport_errors_then_raises(self):
        account = GoodWe("eu.semsportal.com", "443", "user@example.com", "password")
        account.stationDataRequest = Mock(
            side_effect=goodwe_module.requests.exceptions.Timeout("offline")
        )

        with patch("GoodWe.time.sleep") as sleep:
            with self.assertRaises(exceptions.TooManyRetries):
                account.stationDataRequestV2("station-uuid")

        self.assertEqual(account.stationDataRequest.call_count, 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [1, 8, 27])

    def test_legacy_station_data_and_control_requests_handle_json_and_payload(self):
        account = GoodWe("eu.semsportal.com", "443", "user@example.com", "password")
        station_response = make_response({"code": 0})
        with patch("GoodWe.requests.post", return_value=station_response) as post:
            self.assertEqual(account.stationDataRequest("station-uuid"), {"code": 0})
        self.assertEqual(post.call_args.kwargs["data"], {"powerStationId": "station-uuid"})

        control_response = make_response({"code": 0})
        with patch("GoodWe.requests.post", return_value=control_response) as post:
            self.assertEqual(account.setInverterStatus("station-uuid", "serial-1", 2), {"code": 0})
        self.assertEqual(post.call_args.kwargs["data"], {
            "inverterSN": "serial-1",
            "powerStationId": "station-uuid",
            "InverterStatusSettingMark": 1,
            "InverterStatus": 2,
        })

        invalid_json = Mock(url="https://example.test", status_code=200, text="not json")
        invalid_json.json.side_effect = json.JSONDecodeError("invalid", "not json", 0)
        with patch("GoodWe.requests.post", return_value=invalid_json):
            self.assertFalse(account.stationDataRequest("station-uuid"))


class GoodWeSemsWebApiTest(unittest.TestCase):
    def setUp(self):
        self.account = GoodWeSEMSPlus("eu.semsportal.com", "443", "user@example.com", "password")
        self.account.base_url = "https://eu-gateway.semsportal.com/web/sems"
        self.account.token = {
            "uid": "user-id",
            "token": "sems-token",
            "client": "semsPlusWeb",
            "api": self.account.base_url,
        }

    def test_web_device_request_flattens_supported_groups_and_signs_request(self):
        payload = {"data": {"deviceDetailList": [
            {"deviceType": "INVERTER", "statusDetailList": [
                {"snList": ["serial-1"], "detailMap": {"serial-1": {"sn": "serial-1", "name": "inverter"}}},
                None,
            ]},
            {"deviceType": "SMART_METER", "statusDetailList": [
                {"snList": ["meter-1"], "detailMap": {"meter-1": {"sn": "meter-1", "name": "meter"}}},
            ]},
            {"deviceType": "BATTERY", "statusDetailList": []},
            None,
        ]}}
        response = make_response(payload)
        self.account._generate_signature = Mock(return_value="signed-value")

        with patch("GoodWe.requests.get", return_value=response) as get:
            devices = self.account.getWebInverterDevices("station-uuid")

        self.assertEqual([device["sn"] for device in devices], ["serial-1", "meter-1"])
        self.assertEqual([device["deviceType"] for device in devices], ["INVERTER", "SMART_METER"])
        self.assertIsNone(devices[0]["status"])
        self.assertIn("X-Signature", get.call_args.kwargs["headers"])
        self.assertEqual(
            get.call_args.args[0],
            "https://eu-gateway.semsportal.com/web/sems/sems-plant/api/stations/device/all-status?stationId=station-uuid",
        )

    def test_web_telemetry_maps_ac_frequency_temperature_and_four_pv_strings(self):
        factor_values = {
            "Temperature": "36.5",
            "Fac": "50.01",
            "pAc": "4.5",
            "Vac": "241.2",
            "Iac": "18.6",
            "MPPT-1:Vpv": "250.1",
            "MPPT-1:Ipv": "3.1",
            "Vpv2": "251.2",
            "Ipv2": "3.2",
            "MPPT-3:Vpv": "252.3",
            "MPPT-3:Ipv": "3.3",
            "Vpv4": "253.4",
            "Ipv4": "3.4",
        }
        payload = {"data": [{"factors": [
            {"code": code, "data": value} for code, value in factor_values.items()
        ]}]}
        response = make_response(payload)

        with patch("GoodWe.requests.get", return_value=response) as get:
            telemetry = self.account.getWebInverterTelemetry("station-uuid", "serial-1")

        self.assertEqual(telemetry["tempperature"], 36.5)
        self.assertEqual(telemetry["d"], {"fac1": 50.01})
        self.assertEqual(telemetry["output_power"], 4500.0)
        self.assertEqual(telemetry["output_voltage"], 241.2)
        self.assertEqual(telemetry["output_current"], 18.6)
        self.assertEqual(telemetry["pv_input_1"], "250.1V/3.1A")
        self.assertEqual(telemetry["pv_input_2"], "251.2V/3.2A")
        self.assertEqual(telemetry["pv_input_3"], "252.3V/3.3A")
        self.assertEqual(telemetry["pv_input_4"], "253.4V/3.4A")
        self.assertIn("X-Signature", get.call_args.kwargs["headers"])

    def test_web_telemetry_maps_single_and_three_phase_ac_current(self):
        single_phase_payload = {"data": [{"factors": [
            {"code": "Iac1", "data": "7.4"},
        ]}]}
        three_phase_payload = {"data": [{"factors": [
            {"code": "PHASE-A:Iac", "data": "8.1"},
            {"code": "PHASE-B:Iac", "data": "8.7"},
            {"code": "PHASE-C:Iac", "data": "8.3"},
        ]}]}

        with patch("GoodWe.requests.get", side_effect=[
            make_response(single_phase_payload),
            make_response(three_phase_payload),
        ]):
            single_phase = self.account.getWebInverterTelemetry(
                "station-uuid", "single-phase"
            )
            three_phase = self.account.getWebInverterTelemetry(
                "station-uuid", "three-phase"
            )

        self.assertEqual(single_phase["output_current"], 7.4)
        self.assertEqual(three_phase["output_current"], 8.1)
        self.assertEqual(three_phase["output_current_b"], 8.7)
        self.assertEqual(three_phase["output_current_c"], 8.3)

    def test_web_telemetry_maps_phase_a_to_primary_voltage_and_current(self):
        payload = {"data": [{"factors": [
            {"code": "PHASE-A:Vac", "data": "230.1"},
            {"code": "PHASE-B:Vac", "data": "231.2"},
            {"code": "PHASE-C:Vac", "data": "232.3"},
            {"code": "PHASE-A:Iac", "data": "8.1"},
            {"code": "PHASE-B:Iac", "data": "8.7"},
            {"code": "PHASE-C:Iac", "data": "8.3"},
        ]}]}

        with patch("GoodWe.requests.get", return_value=make_response(payload)):
            telemetry = self.account.getWebInverterTelemetry("station-uuid", "serial-1")

        self.assertEqual(telemetry["output_voltage"], 230.1)
        self.assertEqual(telemetry["output_voltage_b"], 231.2)
        self.assertEqual(telemetry["output_voltage_c"], 232.3)
        self.assertEqual(telemetry["output_current"], 8.1)
        self.assertEqual(telemetry["output_current_b"], 8.7)
        self.assertEqual(telemetry["output_current_c"], 8.3)

    def test_web_telemetry_preserves_unparseable_factor_values_safely(self):
        payload = {"data": [None, {"factors": [
            None,
            {"code": 10, "data": "ignored"},
            {"code": "Temperature", "data": "not-a-number"},
            {"code": "Fac", "data": "unknown"},
            {"code": "pAc", "data": "bad-power"},
            {"code": "Vac", "data": "bad-voltage"},
            {"code": "Iac", "data": "bad-current"},
            {"code": "PHASE-A:Iac", "data": "bad-phase-current"},
            {"code": "MPPT-1:Vpv", "data": "bad-v"},
            {"code": "MPPT-1:Ipv", "data": "bad-a"},
        ]}]}

        with patch("GoodWe.requests.get", return_value=make_response(payload)):
            telemetry = self.account.getWebInverterTelemetry("station-uuid", "serial-1")

        self.assertEqual(telemetry["d"]["fac1"], "unknown")
        self.assertNotIn("tempperature", telemetry)
        self.assertNotIn("output_power", telemetry)
        self.assertNotIn("output_voltage", telemetry)
        self.assertNotIn("output_current", telemetry)
        self.assertEqual(telemetry["pv_input_1"], "bad-v/bad-a")

    def test_web_telecounting_maps_energy_counters_and_preserves_unparseable_values(self):
        payload = {"data": [{"factors": [
            {"code": "proPvStatsToday", "data": "3.2"},
            {"code": "proPvStatsTotal", "data": "1200.5"},
            {"code": "proPvStatsWeek", "data": "bad-value"},
            {"code": "proPvStatsMonth", "data": "31.0"},
            {"code": "proPvStatsYear", "data": "400.0"},
            {"code": "ignored", "data": None},
        ]}]}
        response = make_response(payload)

        with patch("GoodWe.requests.get", return_value=response):
            counters = self.account.getWebInverterTelecounting("station-uuid", "serial-1")

        self.assertEqual(counters, {
            "eday": 3.2,
            "etotal": 1200.5,
            "eweek": "bad-value",
            "thismonthetotle": 31.0,
            "eyear": 400.0,
        })

    def test_web_request_failures_return_empty_results(self):
        timeout = goodwe_module.requests.exceptions.Timeout("offline")
        self.account.tokenRequest = Mock()
        with patch("GoodWe.requests.get", side_effect=timeout):
            self.assertEqual(self.account.getWebInverterDevices("station-uuid"), [])
            self.assertEqual(self.account.getWebInverterTelemetry("station-uuid", "serial-1"), {})
            self.assertEqual(self.account.getWebInverterTelecounting("station-uuid", "serial-1"), {})
            self.account.getWebData("station-uuid")
        self.account.tokenRequest.assert_not_called()

    def test_empty_web_device_response_is_logged_at_debug_level(self):
        response_body = '{"data":{"deviceDetailList":[]}}'
        response = make_response({"data": {"deviceDetailList": []}})
        response.text = response_body

        with patch("GoodWe.requests.get", return_value=response):
            with self.assertLogs(level="DEBUG") as captured:
                self.assertEqual(self.account.getWebInverterDevices("station-uuid"), [])

        self.assertTrue(any(response_body in message for message in captured.output))

    def test_empty_or_c0602_device_response_refreshes_session_and_retries_once(self):
        successful_response = make_response({"data": {"deviceDetailList": [
            {"deviceType": "INVERTER", "statusDetailList": [
                {"snList": ["serial-1"], "detailMap": {"serial-1": {"sn": "serial-1"}}},
            ]},
        ]}})
        first_responses = [
            make_response({"data": {"deviceDetailList": []}}),
            make_response({"code": "C0602", "msg": "session expired"}),
        ]

        for first_response in first_responses:
            with self.subTest(payload=first_response.json.return_value):
                account = GoodWeSEMSPlus("eu.semsportal.com", "443", "user@example.com", "password")
                account.base_url = "https://eu-gateway.semsportal.com/web/sems"
                account.token = {
                    "uid": "user-id",
                    "token": "sems-token",
                    "client": "semsPlusWeb",
                    "api": account.base_url,
                }
                account.tokenAvailable = True
                account.tokenRequest = Mock(side_effect=lambda: setattr(account, "tokenAvailable", True) or 200)
                account.getWebInverterTelemetry = Mock(return_value={})
                account.getWebInverterTelecounting = Mock(return_value={})

                with patch("GoodWe.requests.get", side_effect=[first_response, successful_response]) as get:
                    result = account.getWebData("station-uuid")

                self.assertEqual(len(result["inverter"]), 1)
                self.assertEqual(get.call_count, 2)
                account.tokenRequest.assert_called_once_with()

    def test_get_web_data_merges_device_telemetry_counters_and_plugin_defaults(self):
        devices = [
            {"sn": "serial-1", "deviceType": "INVERTER", "status": 1, "name": "inverter"},
            {"deviceType": "INVERTER", "status": 1},
            {"sn": "serial-2", "deviceType": "ENERGY_STORAGE_INTEGRATED_CABINET", "status": 7},
        ]
        self.account.getWebInverterDevices = Mock(return_value=devices)
        self.account.getWebInverterTelemetry = Mock(side_effect=[
            {"output_power": 800.0, "pv_input_1": "200V/4A", "pv_input_2": "201V/4A"},
            {"output_power": 0.0},
        ])
        self.account.getWebInverterTelecounting = Mock(side_effect=[{"etotal": 12.5}, {}])

        result = self.account.getWebData("station-uuid")

        self.assertEqual(result["info"]["powerstation_id"], "station-uuid")
        self.assertEqual([item["sn"] for item in result["inverter"]], ["serial-1", "serial-2"])
        self.assertEqual(result["inverter"][0]["status"], 1)
        self.assertEqual(result["inverter"][0]["etotal"], 12.5)
        self.assertEqual(result["inverter"][0]["pv_input_2"], "201V/4A")
        self.assertEqual(result["inverter"][1]["status"], 0)
        self.assertEqual(result["inverter"][1]["fault_message"], "")
        self.assertEqual(result["inverter"][1]["battery"], "")
        self.assertEqual(self.account.getWebInverterTelemetry.call_count, 2)
        self.account.getWebInverterTelemetry.assert_any_call(
            "station-uuid", "serial-2", "ENERGY_STORAGE_INTEGRATED_CABINET"
        )

    def test_powerstation_api_base_uses_region_only_for_powerstation_routes(self):
        self.assertEqual(
            self.account._resolve_api_base_for_url_part(
                self.account.base_url, "/PowerStation/GetMonitorDetailByPowerstationId"
            ),
            "https://eu.semsportal.com/api",
        )
        self.assertEqual(
            self.account._resolve_api_base_for_url_part(
                self.account.base_url, "/sems-plant/api/stations/device/all-status"
            ),
            self.account.base_url,
        )
        self.account.token["region"] = "au"
        self.assertEqual(
            self.account._resolve_api_base_for_url_part(
                self.account.base_url, "/v3/PowerStation/GetPowerStationList"
            ),
            "https://au.semsportal.com/api",
        )

    def test_semsplus_inverter_control_posts_expected_payload_and_handles_bad_json(self):
        response = make_response({"code": "00000"})
        with patch("GoodWe.requests.post", return_value=response) as post:
            self.assertEqual(self.account.setInverterStatus("station-uuid", "serial-1", 2), {"code": "00000"})

        self.assertEqual(
            post.call_args.args[0],
            "https://eu.semsportal.com/api/PowerStation/SaveRemoteControlInverter",
        )
        self.assertEqual(post.call_args.kwargs["json"], {
            "InverterSN": "serial-1",
            "powerStationId": "station-uuid",
            "InverterStatusSettingMark": 1,
            "InverterStatus": 2,
        })

        invalid_json = Mock(url="https://example.test", status_code=200, text="not json")
        invalid_json.json.side_effect = json.JSONDecodeError("invalid", "not json", 0)
        with patch("GoodWe.requests.post", return_value=invalid_json):
            self.assertFalse(self.account.setInverterStatus("station-uuid", "serial-1", 2))


class GoodWeSemsAuthenticationFallbackTest(unittest.TestCase):
    def test_failed_new_login_falls_back_to_legacy_login(self):
        new_login_response = make_response({"code": "S9999", "msg": "new login rejected"})
        legacy_login_response = make_response({"code": "00000", "data": {"token": "legacy-token"}})
        account = GoodWeSEMSPlus("eu.semsportal.com", "443", "user@example.com", "password")

        with patch(
            "GoodWe.requests.post",
            side_effect=[new_login_response, legacy_login_response],
        ) as post:
            self.assertEqual(account.tokenRequest(), 200)

        self.assertTrue(account.tokenAvailable)
        self.assertEqual(account.token["token"], "legacy-token")
        self.assertEqual(account.base_url, "https://eu.semsportal.com/api")
        self.assertEqual(post.call_args_list[0].args[0], NEW_LOGIN_URL)
        self.assertEqual(post.call_args_list[1].args[0], goodwe_module.OLD_LOGIN_URL)

    def test_login_token_rejects_invalid_payloads_and_uses_fallback_url(self):
        account = GoodWeSEMSPlus("eu.semsportal.com", "443", "user@example.com", "password")

        self.assertIsNone(account._extract_login_token(None))
        self.assertIsNone(account._extract_login_token({"code": "S9999", "msg": "denied"}))
        self.assertIsNone(account._extract_login_token({"code": 0, "data": {}}))
        self.assertEqual(
            account._extract_login_token({"code": 0, "data": {"token": "token"}}, "https://fallback.test"),
            {"token": "token", "api": "https://fallback.test"},
        )


class GoodWeOpenApiTest(unittest.TestCase):
    @patch("GoodWe.requests.post")
    def test_power_station_list_request_uses_configured_regional_server(self, post):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "code": "00000",
            "data": {"dataList": [{"id": "station-first"}, {"id": "station-second"}]},
        }
        post.return_value = response
        account = GoodWeSEMSPlus("au.semsportal.com", "443", "user@example.com", "password")
        account.token = {
            "token": "sems-session-token",
            "client": "semsPlusWeb",
            "api": "https://au-gateway.semsportal.com/web/sems",
        }
        account.base_url = account.token["api"]

        result = account.powerStationListRequest()

        self.assertEqual(result["dataList"][0]["id"], "station-first")
        self.assertEqual(
            post.call_args.args[0],
            "https://au-gateway.semsportal.com/web/sems/sems-plant/api/portal/stations/page",
        )
        self.assertEqual(post.call_args.kwargs["json"], {"current": 1, "size": 100})
        request_headers = post.call_args.kwargs["headers"]
        self.assertEqual(json.loads(request_headers["token"])["token"], "sems-session-token")
        self.assertTrue(request_headers["X-Signature"])

    @patch("GoodWe.requests.post")
    def test_power_station_list_request_refreshes_session_once_on_c0602(self, post):
        expired_response = make_response({"code": "C0602", "msg": "session expired"})
        success_response = make_response({
            "code": "00000",
            "data": {"dataList": [{"id": "station-first"}]},
        })
        post.side_effect = [expired_response, success_response]
        account = GoodWeSEMSPlus("eu.semsportal.com", "443", "user@example.com", "password")
        account.base_url = "https://eu-gateway.semsportal.com/web/sems"
        account.token = {
            "token": "sems-session-token",
            "client": "semsPlusWeb",
            "api": account.base_url,
        }
        account.tokenAvailable = True
        account.tokenRequest = Mock(side_effect=lambda: setattr(account, "tokenAvailable", True) or 200)

        result = account.powerStationListRequest()

        self.assertEqual(result["dataList"][0]["id"], "station-first")
        self.assertEqual(post.call_count, 2)
        account.tokenRequest.assert_called_once_with()

    @patch("GoodWe.requests.post")
    def test_power_station_list_request_rejects_api_error(self, post):
        response = Mock()
        response.json.return_value = {"code": "S9999", "msg": "invalid token"}
        post.return_value = response
        account = GoodWeSEMSPlus("eu.semsportal.com", "443", "user@example.com", "password")
        account.token = {"token": "sems-session-token", "client": "semsPlusWeb"}

        with self.assertRaisesRegex(exceptions.GoodweException, "invalid token"):
            account.powerStationListRequest()

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

    def test_openapi_post_validates_token_api_url_and_response_envelope(self):
        account = GoodWeSEMSPlus("eu.semsportal.com", "443", "user@example.com", "password")
        with self.assertRaisesRegex(exceptions.GoodweException, r"Request a SEMS\+ token"):
            account._openApiPost("/endpoint", {})

        account.token = {"token": "token", "api": "not-a-url"}
        with self.assertRaisesRegex(exceptions.GoodweException, "valid API URL"):
            account._openApiPost("/endpoint", {})

        account.token["api"] = "https://eu-gateway.semsportal.com/web/sems"
        error_response = make_response({"code": "S9999", "msg": "invalid token"})
        invalid_response = make_response(["invalid envelope"])
        with patch("GoodWe.requests.post", side_effect=[error_response, invalid_response]):
            with self.assertRaisesRegex(exceptions.GoodweException, "invalid token"):
                account._openApiPost("/endpoint", {})
            with self.assertRaisesRegex(exceptions.GoodweException, "invalid envelope"):
                account._openApiPost("/endpoint", {})

    @patch("GoodWe.requests.post")
    def test_openapi_telemetry_accepts_single_serial_and_rejects_empty_list(self, post):
        post.return_value = make_response({"code": "00000", "data": {}})
        account = GoodWeSEMSPlus("eu.semsportal.com", "443", "user@example.com", "password")
        account.token = {
            "token": "sems-session-token",
            "api": "https://eu-gateway.semsportal.com/web/sems",
        }

        account.openApiDeviceTelemetryRequest("serial-1", 0)

        self.assertEqual(post.call_args.kwargs["json"], {"sns": ["serial-1"], "deviceType": 0})
        with self.assertRaises(ValueError):
            account.openApiDeviceTelemetryRequest([], 0)


def main():
    logging.basicConfig(format='%(asctime)s - %(levelname)-8s - %(filename)-18s - %(message)s', filename="goodwe_test.log",level=logging.DEBUG)
    logging.info("==== starting test run ====")
    unittest.main()
    logging.info("==== finished test run ====")


if __name__ == "__main__":
    main()
