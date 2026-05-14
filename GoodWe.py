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

OLD_LOGIN_URL = "https://www.semsportal.com/api/v3/Common/CrossLogin"
NEW_LOGIN_URL = "https://semsplus.goodwe.com/web/sems/sems-user/api/v1/auth/cross-login"
_PowerStationURLPart = "/v3/PowerStation/GetMonitorDetailByPowerstationId"
_PowerControlURLPart = "/PowerStation/SaveRemoteControlInverter"
_RequestTimeout = 30
_SuccessCodes = {0, "0", "00000"}
_NewLoginHeaders = {
    "Content-Type": "application/json",
    "Accept": "application/json, */*;q=0.5",
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
        logging.debug("build apiRequestHeaders with token: '" + json.dumps(self.token) + "'" )
        return {
            'User-Agent': 'Domoticz/1.0',
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
            "isLocal": False,
        }
        try:
            r = requests.post(NEW_LOGIN_URL, headers=_NewLoginHeaders, json=login_data, timeout=_RequestTimeout)
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
            r = requests.post(OLD_LOGIN_URL, headers=_DefaultHeaders, data=login_data, timeout=_RequestTimeout)
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
            'User-Agent': 'Domoticz/1.0',
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

        r = requests.post(self.base_url + url, headers=self.apiRequestHeadersV2(), json=payload, timeout=10)
        logging.debug("building SEMS+ station data request on URL: %s which returned status code: %s and response length = %s", r.url, r.status_code, len(r.text))
        try:
            apiResponse = r.json()
        except json.decoder.JSONDecodeError as exp:
            logging.error("SEMS+ station data request JSONDecodeError: %s", exp)
            Domoticz.Error("SEMS+ station data request JSONDecodeError: " + str(exp))
            return False
        logging.debug("response station data request : %s", json.dumps(apiResponse))
        return apiResponse

    def setInverterStatus(self, stationId, inverterSn, mode):
        url = _PowerControlURLPart
        payload = {
            "InverterSN": inverterSn,
            'powerStationId': stationId,
            'InverterStatusSettingMark': 1,
            'InverterStatus': mode
        }

        r = requests.post(self.base_url + url, headers=self.apiRequestHeadersV2(), json=payload, timeout=10)
        logging.debug("building SEMS+ inverter mode post on URL: %s and payload: '%s' which returned status code: %s and response length = %s", r.url, str(payload), r.status_code, len(r.text))
        try:
            apiResponse = r.json()
        except json.decoder.JSONDecodeError as exp:
            logging.error("SEMS+ inverter mode post JSONDecodeError: %s", exp)
            Domoticz.Error("SEMS+ inverter mode post JSONDecodeError: " + str(exp))
            return False
        logging.debug("response inverter mode post : %s", json.dumps(apiResponse))
        return apiResponse
        
