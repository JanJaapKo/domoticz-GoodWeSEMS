# Copyright 2019 Dylian Melgert
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is furnished
# to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN
# AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.


# this module describes the information returned by the GoodWe SEMS portal
# the following terms are used:
# power station: this the site of power generation, typically a physical adress with one or more inverters
# inverter: a piece of equipment that converts the DC power of the panels (grouped in strings) to AC power
# string: a series of solar panels connected to 1 input of the inverter

import json
import requests
import time
import exceptions
import logging
import hashlib
import base64
import uuid
from urllib.parse import urlsplit

OLD_LOGIN_URL = "https://www.semsportal.com/api/v3/Common/CrossLogin"
NEW_LOGIN_URL = "https://semsplus.goodwe.com/web/sems/sems-user/api/v1/auth/cross-login"
_PowerStationURLPart = "/v3/PowerStation/GetMonitorDetailByPowerstationId"
_PowerControlURLPart = "/PowerStation/SaveRemoteControlInverter"
_RequestTimeout = 30
_SuccessCodes = {0, "0", "00000"}
_BrowserUserAgent = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:116.0) "
    "Gecko/20100101 Firefox/116.0"
)

_NewLoginHeaders = {
    "Content-Type": "application/json",
    "Accept": "application/json, */*;q=0.5",
    "token": '{"uid":"","timestamp":0,"token":"","client":"semsPlusWeb","version":"","language":"en"}',
}

_DefaultHeaders = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "token": '{"version":"3.1.1","client":"ios","language":"en"}',
}
_NewLoginFallbackApi = "https://eu-gateway.semsportal.com/web/sems"
_LegacyApiFallback = "https://eu.semsportal.com/api"

try:
    import DomoticzEx as Domoticz
    debug = False
except ImportError:
    import fakeDomoticz as Domoticz
    debug = True

class Inverter:
    """
    A class to describe the methods and properties of a GoodWe inverter
    """
    domoticzDevices = 20
    inverterTemperatureUnit = 1
    inverterStateUnit = 9
    outputCurrentUnit = 2
    outputVoltageUnit = 3
    outputPowerUnit = 4
    inputVoltage1Unit = 5
    inputAmps1Unit = 6
    inputPower1Unit = 14
    inputPower2Unit = 15
    inputPower3Unit = 16
    inputPower4Unit = 17
    inputVoltage2Unit = 7
    inputVoltage3Unit = 10
    inputVoltage4Unit = 12
    inputAmps2Unit = 8
    inputAmps3Unit = 11
    inputAmps4Unit = 13
    outputFreq1Unit = 18
    inverterStateCommand = 19

    def __init__(self, inverterData):
        self._sn = inverterData["sn"]
        self._name = inverterData["name"]

    def __repr__(self):
        return "Inverter type: '" + self._name + "' with serial number: '" + self._sn + "'"

    @property
    def serialNumber(self):
        return self._sn
    
    @property
    def type(self):
        return self._name

class PowerStation:
    """
    A class to describe the methods and properties of a GoodWe PowerStation.
    A power station is typically 1 adress with 1 or more inverters.
    """

    _name = ""
    _address = ""
    _id = ""
    inverters = None
    _firstDevice = 0
    
    def __init__(self, stationData=None, id=None, firstDevice=0):
        self.inverters = {}
        if stationData is None:
            self._id = id
        else:
            self._firstDevice = firstDevice
            self._name = stationData["info"]["stationname"]
            self._address = stationData["info"]["address"]
            self._id = stationData["info"]["powerstation_id"]
            logging.debug("create station with id: '" + self._id + "' and inverters: " + str(len(stationData["inverter"])) )
            self.createInverters(stationData["inverter"])
            
    def __repr__(self):
        return "Station ID: '" + self._id + "', name: '" + self._name + "', inverters: " + str(len(self.inverters))
    
    def createInverters(self, inverterData):
        for inverter in inverterData:
            self.inverters[inverter['sn']] = Inverter(inverter)
            logging.debug("inverter created: '" + str(inverter['sn']) + "'")
            self._firstDevice += self.inverters[inverter['sn']].domoticzDevices
  
    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name
        
    @property
    def numInverters(self):
        return len(self.inverters)

    @property
    def firstFreeDeviceNum(self):
        return self._firstDevice
        
    @firstFreeDeviceNum.setter
    def firstFreeDeviceNum(self,val):
        self._firstDevice = val
        
    def maxDeviceNum(self):
        _maxDeviceNum = 0
        for inv in self.inverters.values():
            _maxDeviceNum += inv.domoticzDevices
        return _maxDeviceNum

class GoodWe:
    """
    A class to describe the methods and properties of a GoodWe account.
    An account consists of 1 or more power stations.
    """

    tokenAvailable = False
    Address = ""
    Port = ""
    token = ""
    default_token = {
        "client": "web",
        "version": "v3.1",
        "language": "en-GB"
    } #default token, will be updated by tokenRequest()

    INVERTER_STATE = {
        -1: 'offline',
        0: 'waiting',
        1: 'generating',
        2: 'error'
    }

    powerStationList = {}
    powerStationIndex = 0

    def __init__(self, Address, Port, User, Password):
        self.Address = "https://" + Address + "/api"
        self.Port = Port
        self.Username = User
        self.Password = Password
        self.base_url = self.Address 
        self.token = self.default_token
        return

    @property
    def numStations(self):
        return len(self.powerStationList)
        
    def createStationV2(self, stationData):
        powerStation = PowerStation(stationData=stationData)
        self.powerStationList.update({1 : powerStation})
        logging.debug("PowerStation created: '" + powerStation.id + "'")

    def apiRequestHeadersV2(self):
        logging.debug("build apiRequestHeaders with token: '%s'", json.dumps(self.token))
        return {
            'User-Agent': _BrowserUserAgent,
            'token': json.dumps(self.token)
        }

    def tokenRequest(self):
        logging.debug("build tokenRequest with UN: '" + self.Username + "', pwd: '" + self.Password +"'")
        url = '/v2/Common/CrossLogin'
        loginPayload = {
            'account': self.Username,
            'pwd': self.Password,
        }

        try:
            r = requests.post(self.base_url + url, headers=self.apiRequestHeadersV2(), data=loginPayload, timeout=10)
        except requests.exceptions.RequestException as exp:
            logging.error("TokenRequestException: " + str(exp))
            Domoticz.Error("TokenRequestException: " + str(exp))
            self.tokenAvailable = False
            return

        #r.raise_for_status()
        logging.debug("building token request on URL: " + r.url + " which returned status code: " + str(r.status_code) + " and response length = " + str(len(r.text)))
        try:
            apiResponse = r.json()
        except json.decoder.JSONDecodeError as exp:
            logging.error("TokenRequestException: " + str(exp))
            Domoticz.Error("TokenRequestException: " + str(exp))
            self.tokenAvailable = False
            return

        try:
            with open("/tmp/goodwe_token_response.json", "w") as f:
                json.dump(apiResponse, f, indent=2)
            logging.info("Saved raw token response to /tmp/goodwe_token_response.json")
            logging.debug("token response: " + json.dumps(apiResponse))
        except Exception as exp:
            logging.error("Failed to save token response: " + str(exp))

        if apiResponse.get("code") == 100005:
            raise exceptions.GoodweException("invalid password or username")

        # Adaptation robuste pour trouver l'URL API
        apiUrl = None
        if "components" in apiResponse and "api" in apiResponse["components"]:
            apiUrl = apiResponse["components"]["api"]
        elif "data" in apiResponse and "api" in apiResponse["data"]:
            apiUrl = apiResponse["data"]["api"]
        elif "api" in apiResponse:
            apiUrl = apiResponse["api"]

        if not apiUrl:
            logging.error("Unexpected API response, no 'api' key: %s", apiResponse)
            Domoticz.Error("Unexpected API response, no 'api' key")
            self.tokenAvailable = False
            return
        if apiResponse == 'Null':
            logging.info("SEMS API Token not received")
            self.tokenAvailable = False
        else:
            self.token = apiResponse.get('data', {})
            logging.debug("SEMS API Token received: " + json.dumps(self.token))
            self.tokenAvailable = True
            self.base_url = apiUrl + "/v2"
        
        return r.status_code

    def stationListRequest(self):
        logging.debug("build stationListRequest")
        url = '/HistoryData/QueryPowerStationByHistory'
        r = requests.post(self.base_url + url, headers=self.apiRequestHeadersV2(), timeout=5)
 
        logging.debug("building station list on URL: " + r.url + " which returned status code: " + str(r.status_code) + " and response length = " + str(len(r.text)))

        return r.status_code

    def stationDataRequestV2(self, stationId):
        for i in range(1, 4):
            try:
                logging.debug("build stationDataRequest for 1 station, attempt: " + str(i))

                responseData = self.stationDataRequest(stationId)
                if not responseData:
                    return
                if isinstance(responseData, dict) and isinstance(responseData.get("inverter"), list):
                    logging.debug("Received normalized SEMS+ telemetry data")
                    return responseData
                try:
                    code = int(responseData['code'])
                except (ValueError, KeyError):
                    raise exceptions.FailureWithoutErrorCode

                if code == 0 and responseData['data'] is not None:
                    #data successfully received
                    return responseData['data']
                elif code == 100001 or code == 100002:
                    #token has expired or is not valid
                    logging.info("Failed to call GoodWe API (no valid token), will be refreshed")
                    self.tokenRequest()
                else:
                    raise exceptions.FailureWithErrorCode(code)
            except requests.exceptions.RequestException as exp:
                logging.error("RequestException: " + str(exp))
                Domoticz.Error("RequestException: " + str(exp))
            time.sleep(i ** 3)
        else:
            raise exceptions.TooManyRetries

    def stationDataRequest(self, stationId):
        url = '/PowerStation/GetMonitorDetailByPowerstationId'
        payload = {
            'powerStationId' : stationId
        }

        r = requests.post(self.base_url + url, headers=self.apiRequestHeadersV2(), data=payload, timeout=10)
        logging.debug("building station data request on URL: " + r.url + " which returned status code: " + str(r.status_code) + " and response length = " + str(len(r.text)))
        try:
            apiResponse = r.json()
        except json.decoder.JSONDecodeError as exp:
            logging.error("RequestException: " + str(exp))
            Domoticz.Error("RequestException: " + str(exp))
            return False
        logging.debug("response station data request : " + json.dumps(r.json()))
        return apiResponse
        
    def setInverterStatus(self, stationId, inverterSn, mode):
        # control inverter going on or off
        # mode 1: ON
        # mode 2: OFF
        url = '/PowerStation/SaveRemoteControlInverter'
        payload = {
            "inverterSN": inverterSn,
            'powerStationId' : stationId,
            'InverterStatusSettingMark': 1,
            'InverterStatus': mode
        }

        r = requests.post(self.base_url + url, headers=self.apiRequestHeadersV2(), data=payload, timeout=10)
        logging.debug("building inverter mode post on URL: " + r.url + " and payload: '"+str(payload)+ "' which returned status code: " + str(r.status_code) + " and response length = " + str(len(r.text)))
        try:
            apiResponse = r.json()
        except json.decoder.JSONDecodeError as exp:
            logging.error("RequestException: " + str(exp))
            Domoticz.Error("RequestException: " + str(exp))
            return False
        logging.debug("response inverter mode post : " + json.dumps(r.json()))
        return apiResponse


class GoodWeSEMSPlus(GoodWe):
    """
    A class to handle GoodWe SEMS+ API, similar to GoodWe but using the new endpoint.
    """

    def _openApiPost(self, path, payload):
        if not isinstance(self.token, dict) or not self.token.get("token"):
            raise exceptions.GoodweException("Request a SEMS+ token before querying OpenAPI endpoints")

        api_url = self.token.get("api") or self.base_url
        parsed_api_url = urlsplit(api_url)
        if not parsed_api_url.scheme or not parsed_api_url.netloc:
            raise exceptions.GoodweException("SEMS+ token response does not contain a valid API URL")
        api_base = f"{parsed_api_url.scheme}://{parsed_api_url.netloc}"
        token_header = json.dumps(self.token)

        response = requests.post(
            api_base + path,
            headers={
                "Authorization": "Bearer " + self.token["token"],
                "token": token_header,
                "Request-Id": str(uuid.uuid4()),
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json=payload,
            timeout=_RequestTimeout,
        )
        response.raise_for_status()
        api_response = response.json()
        if not isinstance(api_response, dict) or api_response.get("code") != "00000":
            message = api_response.get("msg", api_response) if isinstance(api_response, dict) else api_response
            raise exceptions.GoodweException("GoodWe OpenAPI request failed: " + str(message))
        return api_response

    def openApiDeviceListRequest(self, stationId):
        """Query the OpenAPI device list for a station UUID."""
        return self._openApiPost(
            "/goodwe/integration/api/v1/base-info/plant/devices",
            {"searchType": 1, "searchKey": [stationId]},
        )

    def openApiDeviceTelemetryRequest(self, serialNumbers, deviceType):
        """Query real-time telemetry for up to 100 devices of one type."""
        if isinstance(serialNumbers, str):
            serialNumbers = [serialNumbers]
        if not serialNumbers or len(serialNumbers) > 100:
            raise ValueError("serialNumbers must contain between 1 and 100 device serial numbers")

        return self._openApiPost(
            "/goodwe/integration/api/v1/realtime/devices",
            {"sns": list(serialNumbers), "deviceType": deviceType},
        )

    def _is_powerstation_route(self, url_part):
        """Return whether the route should use the legacy PowerStation host."""
        return url_part.startswith("/PowerStation") or url_part.startswith("/v3/PowerStation")

    def _extract_gateway_region(self, api_base):
        """Return the SEMS region prefix from a gateway API base."""
        host = api_base.split("//", 1)[-1].split("/", 1)[0]
        if host.endswith("-gateway.semsportal.com"):
            return host.removesuffix("-gateway.semsportal.com") or None
        if host.endswith(".semsportal.com"):
            return host.split(".", 1)[0] or None
        return None

    def _normalize_powerstation_api_base(self, api_base, url_part):
        """Return the effective API base for PowerStation requests."""
        if not self._is_powerstation_route(url_part):
            return api_base
        if "/web/sems" not in api_base and "/sems/" not in api_base:
            return api_base

        region = None
        if isinstance(self.token, dict) and isinstance(self.token.get("region"), str):
            region = self.token["region"] or None
        if region is None:
            region = self._extract_gateway_region(api_base)

        if region:
            rewritten_base = f"https://{region}.semsportal.com/api"
            logging.debug(
                "SEMS - Rewriting API base from %s to %s for %s",
                api_base,
                rewritten_base,
                url_part,
            )
            return rewritten_base

        logging.debug(
            "SEMS - Rewriting API base from %s to %s for %s",
            api_base,
            _LegacyApiFallback,
            url_part,
        )
        return _LegacyApiFallback

    def _resolve_api_base_for_url_part(self, api_base, url_part):
        """Return the effective API base for a given endpoint path."""
        return self._normalize_powerstation_api_base(api_base, url_part)

    def _hash_password_for_new_login(self, password):
        md5_hex = hashlib.md5(password.encode("utf-8")).hexdigest()
        return base64.b64encode(md5_hex.encode("utf-8")).decode("utf-8")

    def _extract_login_token(self, apiResponse, fallback_api_url=None):
        if not isinstance(apiResponse, dict):
            logging.error("SEMS login response invalid: %s", apiResponse)
            Domoticz.Error("SEMS login response invalid")
            return None
        code = apiResponse.get("code")
        if code not in _SuccessCodes:
            err_msg = apiResponse.get("msg", apiResponse.get("description", "Unknown error"))
            logging.error(
                "SEMS login failed with code: %s, msg: %s, description: %s",
                code,
                apiResponse.get("msg"),
                apiResponse.get("description"),
            )
            Domoticz.Error(f"SEMS login failed with code: {code}, msg: {err_msg}")
            return None
        token_data = apiResponse.get("data")
        if not isinstance(token_data, dict) or not token_data:
            logging.error("SEMS login response missing or invalid token data: %s", apiResponse)
            Domoticz.Error("SEMS login response missing or invalid token data")
            return None

        api_url = apiResponse.get("api") if isinstance(apiResponse.get("api"), str) else token_data.get("api")
        if not api_url:
            api_url = fallback_api_url
        if not api_url:
            logging.error("SEMS login response missing api url: %s", apiResponse)
            Domoticz.Error("SEMS login response missing api url")
            return None

        token_dict = dict(token_data)
        token_dict["api"] = api_url
        if not token_dict.get("token"):
            logging.error("SEMS login response missing token field: %s", apiResponse)
            Domoticz.Error("SEMS login response missing token field")
            return None
        return token_dict

    def _get_new_login_token(self):
        login_data = {
            "account": self.Username,
            "pwd": self._hash_password_for_new_login(self.Password),
            "agreement": 1,
            "isChinese": False,
            "isLocal": True,
        }
        logging.debug("SEMS+ login data "+str(login_data))
        logging.debug("SEMS+ header data "+str(_NewLoginHeaders))
        try:
            # Ensure a browser User-Agent is present while preserving endpoint headers
            headers = {"User-Agent": _BrowserUserAgent, **_NewLoginHeaders}
            r = requests.post(NEW_LOGIN_URL, headers=headers, json=login_data, timeout=_RequestTimeout)
        except requests.exceptions.RequestException as exp:
            logging.error("SEMS+ new login request failed: %s", exp)
            Domoticz.Error("SEMS+ new login request failed: " + str(exp))
            return None

        try:
            apiResponse = r.json()
        except json.decoder.JSONDecodeError as exp:
            logging.error("SEMS+ new login JSONDecodeError: %s", exp)
            Domoticz.Error("SEMS+ new login JSONDecodeError: " + str(exp))
            return None

        return self._extract_login_token(apiResponse, _NewLoginFallbackApi)

    def _get_legacy_login_token(self):
        login_data = json.dumps({"account": self.Username, "pwd": self.Password})
        try:
            # Ensure a browser User-Agent is present while preserving legacy headers
            headers = {"User-Agent": _BrowserUserAgent, **_DefaultHeaders}
            r = requests.post(OLD_LOGIN_URL, headers=headers, data=login_data, timeout=_RequestTimeout)
        except requests.exceptions.RequestException as exp:
            logging.error("SEMS legacy login request failed: %s", exp)
            Domoticz.Error("SEMS legacy login request failed: " + str(exp))
            return None

        try:
            apiResponse = r.json()
        except json.decoder.JSONDecodeError as exp:
            logging.error("SEMS legacy login JSONDecodeError: %s", exp)
            Domoticz.Error("SEMS legacy login JSONDecodeError: " + str(exp))
            return None

        return self._extract_login_token(apiResponse, _LegacyApiFallback)

    def apiRequestHeadersV2(self):
        logging.debug("build SEMS+ apiRequestHeaders with token: '%s'", json.dumps(self.token))
        return {
            "User-Agent": _BrowserUserAgent,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'token': json.dumps(self.token)
        }

    def tokenRequest(self):
        logging.debug("build SEMS+ tokenRequest with username: '%s'", self.Username)
        token_data = self._get_new_login_token()
        if token_data is None:
            logging.info("SEMS+ new login failed, trying legacy SEMS login")
            token_data = self._get_legacy_login_token()

        if token_data is None:
            self.tokenAvailable = False
            return

        self.token = token_data
        self.tokenAvailable = True
        self.base_url = self.token.get("api")
        logging.debug("SEMS+ API Token received: %s", json.dumps(self.token))
        return 200

    def stationDataRequest(self, stationId):
        url = _PowerStationURLPart
        payload = {
            'powerStationId': stationId
        }

        api_base = self._resolve_api_base_for_url_part(self.base_url, url)
        r = requests.post(api_base + url, headers=self.apiRequestHeadersV2(), json=payload, timeout=10)
        logging.debug("building SEMS+ station data request on URL: %s which returned status code: %s and response length = %s", r.url, r.status_code, len(r.text))
        try:
            apiResponse = r.json()
        except json.decoder.JSONDecodeError as exp:
            logging.error("SEMS+ station data request JSONDecodeError: %s", exp)
            Domoticz.Error("SEMS+ station data request JSONDecodeError: " + str(exp))
            return False
        logging.debug("response station data request : %s", json.dumps(apiResponse))

        # If the legacy monitor endpoint returns no usable inverter data,
        # fall back to SEMS+ Web endpoints and synthesize a compatible structure.
        try:
            data = apiResponse.get("data") if isinstance(apiResponse, dict) else None
            if not data or not isinstance(data.get("inverter"), list) or len(data.get("inverter")) == 0:
                logging.info("Legacy SEMS monitor endpoint returned no inverter data; using SEMS+ Web fallback")
                web_data = self.getWebData(stationId)
                return web_data
        except Exception:
            logging.debug("No usable legacy data, attempting SEMS+ Web fallback")
            web_data = self.getWebData(stationId)
            return web_data

        return apiResponse

    def _generate_signature(self, token_data):
        # Generate X-Signature header used by SEMS+ Web endpoints
        try:
            epoch_ms = round(time.time() * 1000)
            digest = hashlib.sha256(f"{epoch_ms}@{token_data.get('uid','')}@{token_data.get('token','')}".encode()).hexdigest()
            sig = f"{digest}@{epoch_ms}"
            return base64.b64encode(sig.encode()).decode()
        except Exception as exp:
            logging.error("Failed to generate X-Signature: %s", exp)
            return None

    def _flatten_web_factors(self, response):
        factors = {}
        for group in response or []:
            if not isinstance(group, dict):
                continue
            for factor in group.get("factors", []):
                if not isinstance(factor, dict) or factor.get("data") is None:
                    continue
                code = factor.get("code")
                if isinstance(code, str):
                    factors[code] = factor.get("data")
        return factors

    def getWebInverterDevices(self, powerStationId):
        url_part = f"/sems-plant/api/stations/device/all-status?stationId={powerStationId}"
        api_base = self._resolve_api_base_for_url_part(self.base_url, url_part)
        headers = self.apiRequestHeadersV2()
        # add X-Signature for web token
        if isinstance(self.token, dict) and self.token.get("client") == "semsPlusWeb":
            sig = self._generate_signature(self.token)
            if sig:
                headers["X-Signature"] = sig
        try:
            r = requests.get(api_base + url_part, headers=headers, timeout=10)
            r.raise_for_status()
            json_response = r.json()
        except Exception as exp:
            logging.error("getWebInverterDevices request failed: %s", exp)
            Domoticz.Error("getWebInverterDevices request failed: " + str(exp))
            return []

        result = json_response.get("data") if isinstance(json_response, dict) else None
        devices = []
        for device_group in (result.get("deviceDetailList", []) if isinstance(result, dict) else []):
            if not isinstance(device_group, dict):
                continue
            device_type = device_group.get("deviceType")
            # accept inverter and energy storage integrated cabinet
            if device_type not in ("INVERTER", "ENERGY_STORAGE_INTEGRATED_CABINET", "SMART_METER"):
                continue
            for status_group in device_group.get("statusDetailList", []):
                if not isinstance(status_group, dict):
                    continue
                detail_map = status_group.get("detailMap", {})
                if not isinstance(detail_map, dict):
                    continue
                for serial_number in status_group.get("snList", []):
                    if not isinstance(serial_number, str):
                        continue
                    detail = detail_map.get(serial_number, {})
                    if isinstance(detail, dict):
                        device = dict(detail)
                        device["deviceType"] = device_type
                        device["status"] = status_group.get("status")
                        devices.append(device)
        return devices

    def getWebInverterTelemetry(self, powerStationId, serialNumber, device_type="INVERTER"):
        url_part = f"/sems-plant/api/equipments/{serialNumber}/telemetry?deviceType={device_type}&pwId={powerStationId}"
        api_base = self._resolve_api_base_for_url_part(self.base_url, url_part)
        headers = self.apiRequestHeadersV2()
        if isinstance(self.token, dict) and self.token.get("client") == "semsPlusWeb":
            sig = self._generate_signature(self.token)
            if sig:
                headers["X-Signature"] = sig
        try:
            r = requests.get(api_base + url_part, headers=headers, timeout=10)
            r.raise_for_status()
            json_response = r.json()
        except Exception as exp:
            logging.error("getWebInverterTelemetry request failed: %s", exp)
            Domoticz.Error("getWebInverterTelemetry request failed: " + str(exp))
            return {}

        factors = self._flatten_web_factors(json_response if isinstance(json_response, list) or isinstance(json_response, dict) and json_response.get("data") is None else json_response.get("data", json_response))
        telemetry = {}
        # basic mappings used by plugin
        if isinstance(factors.get("sn"), str):
            telemetry["sn"] = factors.get("sn")
        if (v := factors.get("Temperature")) is not None:
            try:
                telemetry["tempperature"] = float(v)
            except Exception:
                pass
        # frequency
        fac = factors.get("Fac") or factors.get("fac")
        telemetry.setdefault("d", {})
        if fac is not None:
            try:
                telemetry["d"]["fac1"] = float(fac)
            except Exception:
                telemetry["d"]["fac1"] = fac
        # AC values
        if (v := factors.get("pAc")) is not None:
            try:
                telemetry["output_power"] = float(v) * 1000
            except Exception:
                pass
        if (v := factors.get("Vac")) is not None:
            try:
                telemetry["output_voltage"] = float(v)
            except Exception:
                pass
        if (v := factors.get("Iac")) is not None:
            try:
                telemetry["output_current"] = float(v)
            except Exception:
                pass
        # MPPT inputs
        for idx in range(1, 5):
            vp = factors.get(f"MPPT-{idx}:Vpv") or factors.get(f"Vpv{idx}")
            ip = factors.get(f"MPPT-{idx}:Ipv") or factors.get(f"Ipv{idx}")
            if vp is not None and ip is not None:
                try:
                    vp_f = float(vp)
                    ip_f = float(ip)
                    telemetry[f"pv_input_{idx}"] = "{:.1f}V/{:.1f}A".format(vp_f, ip_f)
                except Exception:
                    telemetry[f"pv_input_{idx}"] = f"{vp}/{ip}"
        return telemetry

    def getWebInverterTelecounting(self, powerStationId, serialNumber, device_type="INVERTER"):
        url_part = f"/sems-plant/api/equipments/{serialNumber}/telecounting?deviceType={device_type}&pwId={powerStationId}"
        api_base = self._resolve_api_base_for_url_part(self.base_url, url_part)
        headers = self.apiRequestHeadersV2()
        if isinstance(self.token, dict) and self.token.get("client") == "semsPlusWeb":
            sig = self._generate_signature(self.token)
            if sig:
                headers["X-Signature"] = sig
        try:
            r = requests.get(api_base + url_part, headers=headers, timeout=10)
            r.raise_for_status()
            json_response = r.json()
        except Exception as exp:
            logging.error("getWebInverterTelecounting request failed: %s", exp)
            Domoticz.Error("getWebInverterTelecounting request failed: " + str(exp))
            return {}

        factors = self._flatten_web_factors(json_response if isinstance(json_response, list) or isinstance(json_response, dict) and json_response.get("data") is None else json_response.get("data", json_response))
        counters = {}
        mapping = (("proPvStatsToday", "eday"), ("proPvStatsTotal", "etotal"), ("proPvStatsWeek", "eweek"), ("proPvStatsMonth", "thismonthetotle"), ("proPvStatsYear", "eyear"))
        for src, tgt in mapping:
            if (v := factors.get(src)) is not None:
                try:
                    counters[tgt] = float(v)
                except Exception:
                    counters[tgt] = v
        return counters

    def getWebData(self, powerStationId):
        # Build the legacy-shaped data object from SEMS+ Web responses
        inverters = []
        devices = self.getWebInverterDevices(powerStationId)
        for device in devices:
            sn = device.get("sn") or device.get("sn")
            if not isinstance(sn, str):
                continue
            device_type = device.get("deviceType", "INVERTER")
            telemetry = self.getWebInverterTelemetry(powerStationId, sn, device_type)
            counters = self.getWebInverterTelecounting(powerStationId, sn, device_type)
            inverter = {}
            inverter.update(device)
            inverter.update(telemetry)
            inverter.update(counters)
            # Normalize fields expected by legacy code
            # plugin expects keys like 'sn','status','fault_message','tempperature','d','output_current','output_voltage','output_power','etotal','pv_input_1'
            inverter.setdefault('fault_message', '')
            inverter.setdefault('status', device.get('status', 0))
            if inverter['status'] not in self.INVERTER_STATE:
                try:
                    inverter['status'] = 1 if float(inverter.get('output_power', 0)) > 0 else 0
                except (TypeError, ValueError):
                    inverter['status'] = 0
            # map pv inputs
            if 'pv_input_1' in telemetry:
                inverter['pv_input_1'] = telemetry.get('pv_input_1')
            if 'pv_input_2' in telemetry:
                inverter['pv_input_2'] = telemetry.get('pv_input_2')
            if 'pv_input_3' in telemetry:
                inverter['pv_input_3'] = telemetry.get('pv_input_3')
            if 'pv_input_4' in telemetry:
                inverter['pv_input_4'] = telemetry.get('pv_input_4')
            # counters may have etotal in kWh; leave as-is
            inverters.append(inverter)
        return {'inverter': inverters}

    def setInverterStatus(self, stationId, inverterSn, mode):
        url = _PowerControlURLPart
        payload = {
            "InverterSN": inverterSn,
            'powerStationId': stationId,
            'InverterStatusSettingMark': 1,
            'InverterStatus': mode
        }

        api_base = self._resolve_api_base_for_url_part(self.base_url, url)
        r = requests.post(api_base + url, headers=self.apiRequestHeadersV2(), json=payload, timeout=10)
        logging.debug("building SEMS+ inverter mode post on URL: %s and payload: '%s' which returned status code: %s and response length = %s", r.url, str(payload), r.status_code, len(r.text))
        try:
            apiResponse = r.json()
        except json.decoder.JSONDecodeError as exp:
            logging.error("SEMS+ inverter mode post JSONDecodeError: %s", exp)
            Domoticz.Error("SEMS+ inverter mode post JSONDecodeError: " + str(exp))
            return False
        logging.debug("response inverter mode post : %s", json.dumps(apiResponse))
        return apiResponse
        
