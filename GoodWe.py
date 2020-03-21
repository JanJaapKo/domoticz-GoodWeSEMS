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
import Domoticz

class Inverter:
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

    def __init__(self, inverterData, startNum):
        self._sn = inverterData["sn"]
        self._name = inverterData["name"]
        self.inverterTemperatureUnit = 1 + startNum
        self.inverterStateUnit = 9 + startNum
        self.outputCurrentUnit = 2 + startNum
        self.outputVoltageUnit = 3 + startNum
        self.outputPowerUnit = 4 + startNum
        self.inputVoltage1Unit = 5 + startNum
        self.inputAmps1Unit = 6 + startNum
        self.inputPower1Unit = 14 + startNum
        self.inputPower2Unit = 15 + startNum
        self.inputPower3Unit = 16 + startNum
        self.inputPower4Unit = 17 + startNum
        self.inputVoltage2Unit = 7 + startNum
        self.inputVoltage3Unit = 10 + startNum
        self.inputVoltage4Unit = 12 + startNum
        self.inputAmps2Unit = 8 + startNum
        self.inputAmps3Unit = 11 + startNum
        self.inputAmps4Unit = 13 + startNum
        self.outputFreq1Unit = 18 + startNum


    def __repr__(self):
        return "Inverter type: '" + self._name + "' with serial number: '" + self._sn + "'"

    @property
    def serialNumber(self):
        return self._sn
    
    @property
    def type(self):
        return self._name

    def createDevices(self, Devices):
        #create domoticz devices
        numDevs = len(Devices)
        if self.inverterTemperatureUnit not in Devices:
            Domoticz.Device(Name="Inverter temperature (SN: " + self.serialNumber + ")",
                            Unit=(self.inverterTemperatureUnit), Type=80, Subtype=5).Create()
        if self.outputCurrentUnit not in Devices:
            Domoticz.Device(Name="Inverter output current (SN: " + self.serialNumber + ")",
                            Unit=(self.outputCurrentUnit), Type=243, Subtype=23).Create()
        if self.outputVoltageUnit not in Devices:
            Domoticz.Device(Name="Inverter output voltage (SN: " + self.serialNumber + ")",
                            Unit=(self.outputVoltageUnit), Type=243, Subtype=8).Create()
        if self.outputPowerUnit not in Devices:
            Domoticz.Device(Name="Inverter output power (SN: " + self.serialNumber + ")",
                            Unit=(self.outputPowerUnit), Type=243, Subtype=29,
                            Switchtype=4, Used=1).Create()
                            
        if self.inverterStateUnit not in Devices:
            Options = {"LevelActions": "||",
                  "LevelNames": "|Offline|Waiting|Generating",
                  "LevelOffHidden": "true",
                  "SelectorStyle": "1"}
            Domoticz.Device(Name="Inverter state (SN: " + self.serialNumber + ")",
                            Unit=(self.inverterStateUnit), TypeName="Selector Switch", Image=1,
                            Options=Options).Create()
                            
        if self.inputVoltage1Unit not in Devices:
            Domoticz.Device(Name="Inverter input 1 voltage (SN: " + self.serialNumber + ")",
                            Unit=(self.inputVoltage1Unit), Type=243, Subtype=8).Create()
        if self.inputAmps1Unit not in Devices:
            Domoticz.Device(Name="Inverter input 1 Current (SN: " + self.serialNumber + ")",
                            Unit=(self.inputAmps1Unit), Type=243, Subtype=23,
                            Switchtype=4, Used=0).Create()
        if self.inputPower1Unit not in Devices:
            Domoticz.Device(Name="Inverter input 1 power (SN: " + self.serialNumber + ")",
                            Unit=(self.inputPower1Unit), Type=243, Subtype=29,
                            Switchtype=4, Used=1).Create()
        if self.inputVoltage2Unit not in Devices:
            Domoticz.Device(Name="Inverter input 2 voltage (SN: " + self.serialNumber + ")",
                            Unit=(self.inputVoltage2Unit), Type=243, Subtype=8, Used=0).Create()
        #input string 2.. 4 are optional. Set devices to not-used
        if self.inputAmps2Unit not in Devices:
            Domoticz.Device(Name="Inverter input 2 Current (SN: " + self.serialNumber + ")",
                            Unit=(self.inputAmps2Unit), Type=243, Subtype=23,
                            Switchtype=4, Used=0).Create()
        if self.inputVoltage3Unit not in Devices:
            Domoticz.Device(Name="Inverter input 3 voltage (SN: " + self.serialNumber + ")",
                            Unit=(self.inputVoltage3Unit), Type=243, Subtype=8, Used=0).Create()
        if self.inputAmps3Unit not in Devices:
            Domoticz.Device(Name="Inverter input 3 Current (SN: " + self.serialNumber + ")",
                            Unit=(self.inputAmps3Unit), Type=243, Subtype=23,
                            Switchtype=4, Used=0).Create()
        if self.inputVoltage4Unit not in Devices:
            Domoticz.Device(Name="Inverter input 4 voltage (SN: " + self.serialNumber + ")",
                            Unit=(self.inputVoltage4Unit), Type=243, Subtype=8, Used=0).Create()
        if self.inputAmps4Unit not in Devices:
            Domoticz.Device(Name="Inverter input 4 Current (SN: " + self.serialNumber + ")",
                            Unit=(self.inputAmps4Unit), Type=243, Subtype=23,
                            Switchtype=4, Used=0).Create()
        if self.inputPower2Unit not in Devices:
            Domoticz.Device(Name="Inverter input 2 power (SN: " + self.serialNumber + ")",
                            Unit=(self.inputPower2Unit), Type=243, Subtype=29,
                            Switchtype=4, Used=0).Create()
        if self.inputPower3Unit not in Devices:
            Domoticz.Device(Name="Inverter input 3 power (SN: " + self.serialNumber + ")",
                            Unit=(self.inputPower3Unit), Type=243, Subtype=29,
                            Switchtype=4, Used=0).Create()
        if self.inputPower4Unit not in Devices:
            Domoticz.Device(Name="Inverter input 4 power (SN: " + self.serialNumber + ")",
                            Unit=(self.inputPower4Unit), Type=243, Subtype=29,
                            Switchtype=4, Used=0).Create()
        if self.outputFreq1Unit not in Devices:
            Domoticz.Device(Name="Inverter output frequency 1 (SN: " + self.serialNumber + ")",
                            Unit=(self.outputFreq1Unit), TypeName="Custom",
                            Used=0).Create()
        if numDevs < len(Devices):
            Domoticz.Log("Number of Devices: " + str(len(Devices)) + ", created for GoodWe inverter (SN: " + self.serialNumber + ")")
        
class PowerStation:
    _name = ""
    _address = ""
    _id = ""
    inverters = {}
    _firstDevice = 0
    
    def __init__(self, stationData=None, id=None, firstDevice=0):
        if stationData is None:
            self._id = id
        else:
            self._firstDevice = firstDevice
            self._name = stationData["pw_name"]
            self._address = stationData["pw_address"]
            self._id = stationData["id"]
            for inverter in stationData["inverters"]:
                self.inverters[inverter['sn']] = Inverter(inverter, self._firstDevice)
                Domoticz.Debug("inverter created: '" + str(self.inverters[inverter['sn']]) + "'")
                self._firstDevice += self.inverters[inverter['sn']].domoticzDevices
            
    def __repr__(self):
        return "Station ID: '" + self._id + "', name: '" + self._name + "', inverters: " + str(len(self.inverters))
        
    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name
        
    @property
    def firstFreeDeviceNum(self):
        return self._firstDevice
        
    @firstFreeDeviceNum.setter
    def firstFreeDeviceNum(self,val):
        self._firstDevice = val
        
    def maxDeviceNum(self):
        for inv in self.inverters:
            _maxDeviceNum += inv.domoticzDevices
        return _maxDeviceNum

class GoodWe:
    tokenAvailable = False
    Address = ""
    Port = ""
    token = {
        "uid": "",
        "timestamp": 0,
        "token": "",
        "client": "web",
        "version": "",
        "language": "en-GB"
    }

    INVERTER_STATE = {
        -1: 'offline',
        0: 'waiting',
        1: 'generating'
    }

    powerStationList = {}
    powerStationIndex = 0

    def __init__(self, Address, Port):
        self.Address = Address
        self.Port = Port
        return

    @property
    def numInverters(self):
        return len(self.powerStationList)
        
    def createStation(self, key, stationData):
        #for key, station in enumerate(apiData["list"]):
        powerStation = PowerStation(stationData=stationData)
        self.powerStationList.update({key : powerStation})
        Domoticz.Log("PowerStation found: " + powerStation.id)
    
    def apiRequestHeaders(self):
        Domoticz.Debug("build apiRequestHeaders with token: '" + json.dumps(self.token) + "'" )
        return {
            'Content-Type': 'application/json; charset=utf-8',
            'Connection': 'keep-alive',
            'Accept': 'Content-Type: application/json; charset=UTF-8',
            'Host': self.Address + ":" + self.Port,
            'User-Agent': 'Domoticz/1.0',
            'token': json.dumps(self.token)
        }

    def tokenRequest(self, Username, Password):
        Domoticz.Debug("build tokenRequest with UN: '" + Username + "', pwd: '" + Password +"'")
        return {
            'Verb': 'POST',
            'URL': '/api/v2/Common/CrossLogin',
            'Data': json.dumps({
                "account": Username,
                "pwd": Password,
                "is_local": True,
                "agreement_agreement": 1
            }),
            'Headers': self.apiRequestHeaders()
        }

    def stationListRequest(self):
        Domoticz.Debug("build stationListRequest")
        return {
            'Verb': 'POST',
            'URL': '/api/v2/HistoryData/QueryPowerStationByHistory',
            'Data': '{}',
            'Headers': self.apiRequestHeaders()
        }

    def stationDataRequest(self):
        Domoticz.Debug("build stationDataRequest with number of stations (len powerStationList) = " + str(self.numInverters))
        powerStation = self.powerStationList[self.powerStationIndex]
        return {
            'Verb': 'POST',
            'URL': '/api/v2/PowerStation/GetMonitorDetailByPowerstationId',
            'Data': json.dumps({
                "powerStationId": powerStation.id
            }),
            'Headers': self.apiRequestHeaders()
        }
