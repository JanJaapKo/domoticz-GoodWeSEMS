# Copyright 2021 Jan-Jaap Kostelijk
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
"""
<plugin key="GoodWeSEMS" name="GoodWe solar inverter via SEMS API" version="3.1.0" author="Jan-Jaap Kostelijk">
    <description>
        <h2>GoodWe inverter (via SEMS portal)</h2>
        <p>This plugin uses the GoodWe SEMS api to retrieve the status information of your GoodWe inverter.</p>
        <h3>Configuration</h3>
        <ul>
            <li>Register your inverter at GoodWe SEMS portal (if not done already): <a href="https://www.semsportal.com">https://www.semsportal.com</a></li>
            <li>Choose one of the following options:</li>
            <ol type="a">
                <li>You have to add one specific station to Domoticz follow the following steps:</li>
                <ol>
                    <li>Login to your account on: <a href="https://www.semsportal.com">www.semsportal.com</a></li>
                    <li>Go to the plant status page for the station you want to add to Domoticz</li>
                    <li>Get the station ID from the URL, this is the sequence of characters after: https://www.semsportal.com/PowerStation/PowerStatusSnMin/, in the pattern:
                    (8 char)-(4 char)-(4 char)-(4 char)-(12 char), also known as a UUID </li>
                    <li>Add the power station ID to the hardware configuration (mandatory)</li>
                </ol>
                <li>Not possible at this moment: If you want all of your stations added to Domoticz you only have to enter your login information below</li>
            </ol>
        </ul>
    </description>
    <params>
        <param field="Address" label="SEMS Server" width="100px" required="true">
            <options>
                <option label="Europe" value="eu.semsportal.com"/>
                <option label="Australia" value="au.semsportal.com"/>
                <option label="Global" value="www.semsportal.com" default="true"/>
            </options>
        </param>
        <param field="Port" label="SEMS API Port" width="30px" required="true" default="443"/>
        <param field="Username" label="E-Mail address" width="300px" required="true"/>
        <param field="Password" label="Password" width="100px" required="true" password="true"/>
        <param field="Mode1" label="Power Station ID (mandatory)" width="300px"/>
        <param field="Mode2" label="Refresh interval" width="75px">
            <options>
                <option label="30s" value="3"/>
                <option label="1m" value="6"/>
                <option label="5m" value="30" default="true"/>
                <option label="10m" value="60"/>
                <option label="15m" value="90"/>
                <option label="30m" value="180"/>
            </options>
        </param>
        <param field="Mode3" label="Peak power [W]" width="300px">
            <description>Optional: Peak power, supply values (separated by ';'): total power; power per string</description>
        </param>
        <param field="Mode6" label="Log level" width="75px">
            <options>
                <option label="Verbose" value="Verbose"/>
                <option label="Debug" value="Debug"/>
                <option label="Normal" value="Normal" default="true"/>
            </options>
        </param>
    </params>
</plugin>
"""
import json
#import Domoticz
import DomoticzEx as Domoticz
import sys, time
from datetime import datetime, timedelta
from GoodWe import GoodWe
from GoodWe import PowerStation
import exceptions
import logging

class GoodWeSEMSPlugin:
    httpConn = None
    runAgain = 6
    devicesUpdated = False
    goodWeAccount = None
    logger = None    
    
    baseDeviceIndex = 0
    maxDeviceIndex = 0

    def __init__(self):
        startNum = 0
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
        return

    def apiConnection(self):
        if Parameters["Port"] == "443":
            return Domoticz.Connection(Name="SEMS Portal API", Transport="TCP/IP", Protocol="HTTPS",
                                       Address=Parameters["Address"], Port=Parameters["Port"])
        else:
            return Domoticz.Connection(Name="SEMS Portal API", Transport="TCP/IP", Protocol="HTTP",
                                       Address=Parameters["Address"], Port=Parameters["Port"])

    def startDeviceUpdateV2(self):
        logging.debug("startDeviceUpdate, token availability: '" + str(self.goodWeAccount.tokenAvailable)+ "'")
        if not self.goodWeAccount.tokenAvailable:
            self.goodWeAccount.powerStationList = {}
            self.goodWeAccount.powerStationIndex = 0
            self.devicesUpdated = False
            try:
                self.goodWeAccount.tokenRequest()
            except (exceptions.GoodweException, exceptions.FailureWithMessage, exceptions.FailureWithoutMessage) as exp:
                logging.error("Failed to request data: " + str(exp))
                Domoticz.Error("Failed to request data: " + str(exp))
                return
            
        if self.goodWeAccount.tokenAvailable:
            try:
                DeviceData = self.goodWeAccount.stationDataRequestV2(Parameters["Mode1"])
            except (exceptions.TooManyRetries, exceptions.FailureWithErrorCode, exceptions.FailureWithoutErrorCode) as exp:
                logging.error("Failed to request data: " + str(exp))
                Domoticz.Error("Failed to request data: " + str(exp))
                return
            self.goodWeAccount.createStationV2(DeviceData)
            self.updateDevices(DeviceData)

    def updateDevices(self, apiData):
        theStation = self.goodWeAccount.powerStationList[1]
        for inverter in apiData["inverter"]:
            logging.debug("inverter found with SN: '" + inverter["sn"] + "'")
            if inverter["sn"] in theStation.inverters:
                #theStation.inverters[inverter["sn"]].createDevices(Devices)
                self.createDevices(inverter["sn"])
                
                theInverter = theStation.inverters[inverter["sn"]]

                if len(inverter['fault_message']) > 0:
                    Domoticz.Log("Fault message from GoodWe inverter (SN: " + inverter["sn"] + "): '" + str(inverter['fault_message']) + "'")
                    logging.info("Fault message from GoodWe inverter (SN: " + inverter["sn"] + "): '" + str(inverter['fault_message']) + "'")
                Domoticz.Log("Status of GoodWe inverter (SN: " + inverter["sn"] + "): '" + str(inverter["status"]) + ' ' + self.goodWeAccount.INVERTER_STATE[inverter["status"]] + "'")
                logging.info("Status of GoodWe inverter (SN: " + inverter["sn"] + "): '" + str(inverter["status"]) + ' ' + self.goodWeAccount.INVERTER_STATE[inverter["status"]] + "'")
                UpdateDevice(inverter["sn"], theInverter.inverterStateUnit, inverter["status"]+1, str((inverter["status"]+2)*10), AlwaysUpdate=True)
                #Devices[inverter["sn"]].Unit[theInverter.inverterStateUnit].Update(nValue=inverter["status"]+1, sValue=str((inverter["status"]+2)*10))
                if self.goodWeAccount.INVERTER_STATE[inverter["status"]] == 'generating':
                    logging.debug("inverter generating, log temp")
                    UpdateDevice(inverter["sn"],theInverter.inverterTemperatureUnit, 0, str(inverter["tempperature"]))
                    UpdateDevice(inverter["sn"],theInverter.outputFreq1Unit, 0, str(inverter["d"]["fac1"]))

                UpdateDevice(inverter["sn"], theInverter.outputCurrentUnit, 0, str(inverter["output_current"]), AlwaysUpdate=True)
                UpdateDevice(inverter["sn"], theInverter.outputVoltageUnit, 0, str(inverter["output_voltage"]), AlwaysUpdate=True)
                UpdateDevice(inverter["sn"], theInverter.outputPowerUnit, 0, str(inverter["output_power"]) + ";" + str(inverter["etotal"] * 1000), AlwaysUpdate=True)
                inputVoltage,inputAmps = inverter["pv_input_1"].split('/')
                inputPower = float(inputVoltage[:-1]) * float(inputAmps[:-1]) #calculate the power based on P = I * V in Watt
                UpdateDevice(inverter["sn"], theInverter.inputVoltage1Unit, 0, inputVoltage, AlwaysUpdate=True)
                UpdateDevice(inverter["sn"], theInverter.inputAmps1Unit, 0, inputAmps, AlwaysUpdate=True)

                newCounter = calculateNewEnergy(inverter["sn"], theInverter.inputPower1Unit, inputPower)
                UpdateDevice(inverter["sn"],theInverter.inputPower1Unit, 0, "{:5.1f};{:10.2f}".format(inputPower, newCounter), AlwaysUpdate=True)

                if "pv_input_2" in inverter:
                    logging.debug("Second string found")
                    inputVoltage,inputAmps = inverter["pv_input_2"].split('/')
                    UpdateDevice(inverter["sn"],theInverter.inputVoltage2Unit, 0, inputVoltage, AlwaysUpdate=True)
                    UpdateDevice(inverter["sn"],theInverter.inputAmps2Unit, 0, inputAmps, AlwaysUpdate=True)
                    inputPower = (float(inputVoltage[:-1])) * (float(inputAmps[:-1]))
                    newCounter = calculateNewEnergy(inverter["sn"], theInverter.inputPower2Unit, inputPower)
                    UpdateDevice(inverter["sn"],theInverter.inputPower2Unit, 0, "{:5.1f};{:10.2f}".format(inputPower, newCounter), AlwaysUpdate=True)
                if "pv_input_3" in inverter:
                    logging.debug("Third string found")
                    inputVoltage,inputAmps = inverter["pv_input_3"].split('/')
                    UpdateDevice(inverter["sn"],theInverter.inputVoltage3Unit, 0, inputVoltage, AlwaysUpdate=True)
                    UpdateDevice(inverter["sn"],theInverter.inputAmps3Unit, 0, inputAmps, AlwaysUpdate=True)
                    inputPower = float(inputVoltage[:-1]) * float(inputAmps[:-1])
                    newCounter = calculateNewEnergy(inverter["sn"], theInverter.inputPower3Unit, inputPower)
                    UpdateDevice(inverter["sn"],theInverter.inputPower3Unit, 0, "{:5.1f};{:10.2f}".format(inputPower, newCounter), AlwaysUpdate=True)
                if "pv_input_4" in inverter:
                    logging.debug("Fourth string found")
                    inputVoltage,inputAmps = inverter["pv_input_4"].split('/')
                    UpdateDevice(inverter["sn"],theInverter.inputVoltage4Unit, 0, inputVoltage, AlwaysUpdate=True)
                    UpdateDevice(inverter["sn"],theInverter.inputAmps4Unit, 0, inputAmps, AlwaysUpdate=True)
                    inputPower = float(inputVoltage[:-1]) * float(inputAmps[:-1])
                    newCounter = calculateNewEnergy(inverter["sn"], theInverter.inputPower4Unit, inputPower)
                    UpdateDevice(inverter["sn"],theInverter.inputPower4Unit, 0, "{:5.1f};{:10.2f}".format(inputPower, newCounter), AlwaysUpdate=True)
                #log data of battery
                Domoticz.Debug("Battery values: battery: '{0}', bms_status: '{1}', battery_power: '{2}'".format(inverter["battery"],inverter["bms_status"],inverter["battery_power"]))
                logging.debug("Battery values: battery: '{0}', bms_status: '{1}', battery_power: '{2}'".format(inverter["battery"],inverter["bms_status"],inverter["battery_power"]))

    def createDevices(self, serialNumber):
        #create domoticz devices
        logging.info("creating units for device with serial number: "+ serialNumber)
        thisDevice = Domoticz.Device(DeviceID=serialNumber) #use serial number as identifier for Domoticz.Device instance
        numDevs = len(Devices[serialNumber].Units)
        if self.inverterTemperatureUnit not in Devices[serialNumber].Units:
            Domoticz.Unit(Name="Inverter temperature (SN: " + serialNumber + ")",
                            Unit=(self.inverterTemperatureUnit), Type=80, Subtype=5, DeviceID=serialNumber).Create()
        #if self.outputCurrentUnit not in Devices:
        if self.outputCurrentUnit not in Devices[serialNumber].Units:
            Domoticz.Unit(Name="Inverter output current (SN: " + serialNumber + ")",
                            Unit=(self.outputCurrentUnit), Type=243, Subtype=23, DeviceID=serialNumber).Create()
        if self.outputVoltageUnit not in Devices[serialNumber].Units:
            Domoticz.Unit(Name="Inverter output voltage (SN: " + serialNumber + ")",
                            Unit=(self.outputVoltageUnit), Type=243, Subtype=8, DeviceID=serialNumber).Create()
        if self.outputPowerUnit not in Devices[serialNumber].Units:
            Domoticz.Unit(Name="Inverter output power (SN: " + serialNumber + ")",
                            Unit=(self.outputPowerUnit), Type=243, Subtype=29,
                            Switchtype=4, Used=1, DeviceID=serialNumber).Create()
                            
        if self.inverterStateUnit not in Devices[serialNumber].Units:
            Options = {"LevelActions": "|||",
                  "LevelNames": "|Offline|Waiting|Generating|Error",
                  "LevelOffHidden": "true",
                  "SelectorStyle": "1"}
            Domoticz.Unit(Name="Inverter state (SN: " + serialNumber + ")",
                            Unit=(self.inverterStateUnit), TypeName="Selector Switch", Image=1,
                            Options=Options, Used=1, DeviceID=serialNumber).Create()
                            
        if self.inputVoltage1Unit not in Devices[serialNumber].Units:
            Domoticz.Unit(Name="Inverter input 1 voltage (SN: " + serialNumber + ")",
                            Unit=(self.inputVoltage1Unit), Type=243, Subtype=8, 
                            DeviceID=serialNumber).Create()
        if self.inputAmps1Unit not in Devices[serialNumber].Units:
            Domoticz.Unit(Name="Inverter input 1 Current (SN: " + serialNumber + ")",
                            Unit=(self.inputAmps1Unit), Type=243, Subtype=23,
                            Switchtype=4, Used=0, DeviceID=serialNumber).Create()
        if self.inputPower1Unit not in Devices[serialNumber].Units:
            Domoticz.Unit(Name="Inverter input 1 power (SN: " + serialNumber + ")",
                            Unit=(self.inputPower1Unit), Type=243, Subtype=29,
                            Switchtype=4, Used=1, DeviceID=serialNumber).Create()
        if self.inputVoltage2Unit not in Devices[serialNumber].Units:
            Domoticz.Unit(Name="Inverter input 2 voltage (SN: " + serialNumber + ")",
                            Unit=(self.inputVoltage2Unit), Type=243, Subtype=8, Used=0, 
                            DeviceID=serialNumber).Create()
        #input string 2.. 4 are optional. Set devices to not-used
        if self.inputAmps2Unit not in Devices[serialNumber].Units:
            Domoticz.Unit(Name="Inverter input 2 Current (SN: " + serialNumber + ")",
                            Unit=(self.inputAmps2Unit), Type=243, Subtype=23,
                            Switchtype=4, Used=0, DeviceID=serialNumber).Create()
        if self.inputVoltage3Unit not in Devices[serialNumber].Units:
            Domoticz.Unit(Name="Inverter input 3 voltage (SN: " + serialNumber + ")",
                            Unit=(self.inputVoltage3Unit), Type=243, Subtype=8, Used=0, 
                            DeviceID=serialNumber).Create()
        if self.inputAmps3Unit not in Devices[serialNumber].Units:
            Domoticz.Unit(Name="Inverter input 3 Current (SN: " + serialNumber + ")",
                            Unit=(self.inputAmps3Unit), Type=243, Subtype=23,
                            Switchtype=4, Used=0, DeviceID=serialNumber).Create()
        if self.inputVoltage4Unit not in Devices[serialNumber].Units:
            Domoticz.Unit(Name="Inverter input 4 voltage (SN: " + serialNumber + ")",
                            Unit=(self.inputVoltage4Unit), Type=243, Subtype=8, Used=0, 
                            DeviceID=serialNumber).Create()
        if self.inputAmps4Unit not in Devices[serialNumber].Units:
            Domoticz.Unit(Name="Inverter input 4 Current (SN: " + serialNumber + ")",
                            Unit=(self.inputAmps4Unit), Type=243, Subtype=23,
                            Switchtype=4, Used=0, DeviceID=serialNumber).Create()
        if self.inputPower2Unit not in Devices[serialNumber].Units:
            Domoticz.Unit(Name="Inverter input 2 power (SN: " + serialNumber + ")",
                            Unit=(self.inputPower2Unit), Type=243, Subtype=29,
                            Switchtype=4, Used=0, DeviceID=serialNumber).Create()
        if self.inputPower3Unit not in Devices[serialNumber].Units:
            Domoticz.Unit(Name="Inverter input 3 power (SN: " + serialNumber + ")",
                            Unit=(self.inputPower3Unit), Type=243, Subtype=29,
                            Switchtype=4, Used=0, DeviceID=serialNumber).Create()
        if self.inputPower4Unit not in Devices[serialNumber].Units:
            Domoticz.Unit(Name="Inverter input 4 power (SN: " + serialNumber + ")",
                            Unit=(self.inputPower4Unit), Type=243, Subtype=29,
                            Switchtype=4, Used=0, DeviceID=serialNumber).Create()
        if self.outputFreq1Unit not in Devices[serialNumber].Units:
            Domoticz.Unit(Name="Inverter output frequency 1 (SN: " + serialNumber + ")",
                            Unit=(self.outputFreq1Unit), TypeName="Custom",
                            Used=0, DeviceID=serialNumber).Create()
        logging.info("finished creating devices, current count: "+str(len(Devices[serialNumber].Units)))
        if numDevs < len(Devices[serialNumber].Units):
            if "54200DSN196R0358" in Devices:
                Domoticz.Debug("Number of Units: " + str(len(Devices[serialNumber].Units)) + ", number of units: " + str(len(Devices["54200DSN196R0358"].Units)) + ")")
            else:
                Domoticz.Debug("no Device with Serial Number found")
            #Domoticz.Log("Number of Devices: " + str(len(Devices[serialNumber].Units)) + ", created for GoodWe inverter (SN: " + serialNumber + ")")
        

    def onStart(self):
        self.logger = logging.getLogger('root')
        self.log_filename = "goodwe "+Parameters["Name"]+".log"
        if Parameters["Mode6"] == "Verbose":
            Domoticz.Debugging(1)
            logging.basicConfig(format='%(asctime)s - %(levelname)-8s - %(filename)-18s - %(message)s', filename=self.log_filename,level=logging.DEBUG)
            Domoticz.Status("Starting Goodwe SEMS API plugin, logging to file {0}".format(self.log_filename))
            DumpConfigToLog()
        elif Parameters["Mode6"] == "Debug":
            Domoticz.Debugging(2)
            logging.basicConfig(format='%(asctime)s - %(levelname)-8s - %(filename)-18s - %(message)s', filename=self.log_filename,level=logging.DEBUG)
            Domoticz.Status("Starting Goodwe SEMS API plugin, logging to file {0}".format(self.log_filename))
            DumpConfigToLog()
        else:
            logging.basicConfig(format='%(asctime)s - %(levelname)-8s - %(filename)-18s - %(message)s', filename=self.log_filename,level=logging.INFO)
            Domoticz.Status("Starting Goodwe SEMS API plugin, logging to file {0}".format(self.log_filename))
        
        logging.info("starting plugin version "+Parameters["Version"])

        self.goodWeAccount = GoodWe(Parameters["Address"], Parameters["Port"], Parameters["Username"], Parameters["Password"])
        self.runAgain = int(Parameters["Mode2"])

        if len(Parameters["Mode1"]) == 0:
            Domoticz.Error("No Power Station ID provided, exiting")
            logging.error("No Power Station ID provided, exiting")
            return
            
        self.startDeviceUpdateV2()

    def onStop(self):
        Domoticz.Log("onStop - Plugin is stopping.")
        logging.info("onStop - Plugin is stopping.")
        if self.httpConn is not None:
            self.httpConn.Disconnect()

    def onConnect(self, Connection, Status, Description):
        logging.debug("onConnect: Status: '" + str(Status) + "', Description: '" + Description + "'")
        if (Status == 0):
            logging.debug("Connected to SEMS portal API successfully.")
            self.startDeviceUpdate(Connection)
        else:
            Domoticz.Log("Failed to connect (" + str(Status) + ") to: " + Parameters["Address"] + ":" + Parameters[
                "Port"] + " with error: " + Description)
            logging.info("Failed to connect (" + str(Status) + ") to: " + Parameters["Address"] + ":" + Parameters[
                "Port"] + " with error: " + Description)

    def onMessage(self, Connection, Data):
        logging.debug("onMessage: data received: Data : '" + str(Data) + "'")
        Domoticz.Error("onMessage called unexpectedly: data received: Data : '" + str(Data) + "'")
        return
        status = int(Data["Status"])

        if status == 200:
            apiUrl = ""
            try:
                #apiResponse sometimes contains invalid data, catch the exception
                if "Data" in Data:
                    responseText = Data["Data"].decode("utf-8", "ignore")
                else:
                    responseText = ""
                    logging.debug("onMessage: no data found in data")
                    return
                apiResponse = json.loads(responseText)
                apiUrl = apiResponse["components"]["api"]
                apiData = apiResponse["data"]
            except json.JSONDecodeError as err:
                msg, doc, pos = err.args
                logging.error(msg)
                Domoticz.Error(msg)
                apiResponse = None
                logging.debug("The faulty message: '" + doc)

            if "api/v2/Common/CrossLogin" in apiUrl:
                logging.debug("message received: CrossLogin")
                if apiData == 'Null':
                    Domoticz.Log("SEMS API Token not received")
                    logging.info("SEMS API Token not received")
                    self.goodWeAccount.tokenAvailable = False
                    self.httpConn.Disconnect()
                    #self.httpConn = None
                else:
                    logging.debug("message apiData: '" + str(apiData) + "'")
                    self.goodWeAccount.token = apiData
                    logging.debug("SEMS API Token: " + json.dumps(self.goodWeAccount.token))
                    self.goodWeAccount.tokenAvailable = True
                    #request list of stations on this account
                    Connection.Send(self.goodWeAccount.stationListRequest())

            elif "/api/v2/HistoryData/QueryPowerStationByHistory" in apiUrl:
                logging.debug("message received: QueryPowerStationByHistory")
                if apiData is None or len(apiData)==0:
                    Domoticz.Log("Power station history not received")
                    logging.info("Power station history not received")
                    self.httpConn.Disconnect()
                    #self.httpConn = None
                else:
                    logging.debug("message apiData: '" + str(apiData) + "'")
                    for stations in apiData["list"]:
                        for data in stations:
                            logging.debug("station element: '"+ str(data) + "', value: '" + str(stations[data]) +"'")
                    for key, station in enumerate(apiData["list"]):
                        if len(Parameters["Mode1"]) <= 0 or (len(Parameters["Mode1"]) > 0 and station["id"] == Parameters["Mode1"]):
                            #add all found stations if no ID entered, else only log the one that matches the ID
                            self.goodWeAccount.createStation(key, station)
                            Domoticz.Log("Station found: " + station["id"])
                            logging.info("Station found: " + station["id"])

                    Connection.Send(self.goodWeAccount.stationDataRequest(self.baseDeviceIndex))

            elif "api/v2/PowerStation/GetMonitorDetailByPowerstationId" in apiUrl:
                logging.debug("message received: GetMonitorDetailByPowerstationId")
                if apiData is None or len(apiData) == 0:
                    Domoticz.Error("No station data received from GoodWe SEMS API (Station ID: " + str(self.goodWeAccount.powerStationList[
                        self.goodWeAccount.powerStationIndex]) + ")")
                    logging.error("No station data received from GoodWe SEMS API (Station ID: " + str(self.goodWeAccount.powerStationList[
                        self.goodWeAccount.powerStationIndex]) + ")")
                    self.goodWeAccount.tokenAvailable = False
                else:
                    #logging.debug("message apiData: '" + str(apiData) + "'")
                    Domoticz.Log("Station data received from GoodWe SEMS API ('" + str(self.goodWeAccount.powerStationList[
                        self.goodWeAccount.powerStationIndex]) + "', index : '" + str(self.goodWeAccount.powerStationIndex)+ "')")
                    logging.info("Station data received from GoodWe SEMS API ('" + str(self.goodWeAccount.powerStationList[
                        self.goodWeAccount.powerStationIndex]) + "', index : '" + str(self.goodWeAccount.powerStationIndex)+ "')")
                    theStation = self.goodWeAccount.powerStationList[self.goodWeAccount.powerStationIndex]

                    for inverter in apiData["inverter"]:
                        logging.debug("inverter found with SN: '" + inverter["sn"] + "'")
                        if inverter["sn"] in theStation.inverters:
                            #stheStation.inverters[inverter["sn"]].createDevices(Devices)
                            self.createDevices(inverter["sn"])
                            logging.debug("Details d in inverter: '" + str(inverter['d']) + "'")
                            
                            theInverter = theStation.inverters[inverter["sn"]]

                            if len(inverter['fault_message']) > 0:
                                Domoticz.Log("Fault message from GoodWe inverter (SN: " + inverter["sn"] + "): '" + str(inverter['fault_message']) + "'")
                                logging.info("Fault message from GoodWe inverter (SN: " + inverter["sn"] + "): '" + str(inverter['fault_message']) + "'")
                            Domoticz.Log("Status of GoodWe inverter (SN: " + inverter["sn"] + "): '" + str(inverter["status"]) + ' ' + self.goodWeAccount.INVERTER_STATE[inverter["status"]] + "'")
                            logging.info("Status of GoodWe inverter (SN: " + inverter["sn"] + "): '" + str(inverter["status"]) + ' ' + self.goodWeAccount.INVERTER_STATE[inverter["status"]] + "'")
                            Devices[theInverter.inverterStateUnit].Update(nValue=inverter["status"]+1, sValue=str((inverter["status"]+2)*10))
                            if self.goodWeAccount.INVERTER_STATE[inverter["status"]] == 'generating':
                                logging.debug("inverter generating, log temp")
                                UpdateDevice(theInverter.inverterTemperatureUnit, 0, str(inverter["tempperature"]))
                                UpdateDevice(theInverter.outputFreq1Unit, 0, str(inverter["d"]["fac1"]))

                            UpdateDevice(theInverter.outputCurrentUnit, 0, str(inverter["output_current"]), AlwaysUpdate=True)
                            UpdateDevice(theInverter.outputVoltageUnit, 0, str(inverter["output_voltage"]), AlwaysUpdate=True)
                            UpdateDevice(theInverter.outputPowerUnit, 0, str(inverter["output_power"]) + ";" + str(inverter["etotal"] * 1000), AlwaysUpdate=True)
                            inputVoltage,inputAmps = inverter["pv_input_1"].split('/')
                            inputPower = (float(inputVoltage[:-1])) * (float(inputAmps[:-1]))
                            UpdateDevice(theInverter.inputVoltage1Unit, 0, inputVoltage, AlwaysUpdate=True)
                            UpdateDevice(theInverter.inputAmps1Unit, 0, inputAmps, AlwaysUpdate=True)
                            UpdateDevice(theInverter.inputPower1Unit, 0, str(inputPower) + ";0", AlwaysUpdate=True)
                            #test to log cumulative counting
                            previousPower,currentCount = Devices[theInverter.inputPowerTest].sValue.split(";") 
                            newCounter =  inputPower + float(currentCount) 
                            UpdateDevice(theInverter.inputPowerTest, 0, str(inputPower) + ";"  + str(newCounter), AlwaysUpdate=True)
                            logging.debug("test previousPower, currentCount, newCounter = " + str(previousPower) + ", " + str(currentCount) + ", " + str(newCounter))
                            if "pv_input_2" in inverter:
                                logging.debug("Second string found")
                                inputVoltage,inputAmps = inverter["pv_input_2"].split('/')
                                UpdateDevice(theInverter.inputVoltage2Unit, 0, inputVoltage, AlwaysUpdate=True)
                                UpdateDevice(theInverter.inputAmps2Unit, 0, inputAmps, AlwaysUpdate=True)
                                inputPower = (float(inputVoltage[:-1])) * (float(inputAmps[:-1]))
                                UpdateDevice(theInverter.inputPower2Unit, 0, str(inputPower) + ";0", AlwaysUpdate=True)
                            if "pv_input_3" in inverter:
                                logging.debug("Third string found")
                                inputVoltage,inputAmps = inverter["pv_input_3"].split('/')
                                UpdateDevice(theInverter.inputVoltage3Unit, 0, inputVoltage, AlwaysUpdate=True)
                                UpdateDevice(theInverter.inputAmps3Unit, 0, inputAmps, AlwaysUpdate=True)
                                inputPower = float(inputVoltage[:-1]) * float(inputAmps[:-1])
                                UpdateDevice(theInverter.inputPower3Unit, 0, str(inputPower) + ";0", AlwaysUpdate=True)
                            if "pv_input_4" in inverter:
                                logging.debug("Fourth string found")
                                inputVoltage,inputAmps = inverter["pv_input_4"].split('/')
                                UpdateDevice(theInverter.inputVoltage4Unit, 0, inputVoltage, AlwaysUpdate=True)
                                UpdateDevice(theInverter.inputAmps4Unit, 0, inputAmps, AlwaysUpdate=True)
                                inputPower = float(inputVoltage[:-1]) * float(inputAmps[:-1])
                                UpdateDevice(theInverter.inputPower4Unit, 0, str(inputPower) + ";0", AlwaysUpdate=True)
                        else:
                            Domoticz.Log("Unknown inverter found with S/N: '" + inverter["sn"] +"'.")
                            logging.info("Unknown inverter found with S/N: '" + inverter["sn"] +"'.")

                if self.goodWeAccount.powerStationIndex == (len(self.goodWeAccount.powerStationList) - 1):
                    logging.debug("Last station of list found")
                    if self.runAgain > 2:
                        logging.info("Next active heartbeat far away, disconnecting and dropping connection.")
                        self.httpConn.Disconnect()

                    self.devicesUpdated = True
                else:
                    logging.debug("Retrieving next station data (ID: " + self.goodWeAccount.powerStationList[self.baseDeviceIndex] + ")")
                    self.baseDeviceIndex += 1
                    Connection.Send(self.goodWeAccount.stationDataRequest(self.baseDeviceIndex))

        elif status == 302:
            logging.error("GoodWe SEMS API returned a Page Moved Error.")
            Domoticz.Error("GoodWe SEMS API returned a Page Moved Error.")
        elif status == 400:
            logging.error("GoodWe SEMS API returned a Bad Request Error.")
            Domoticz.Error("GoodWe SEMS API returned a Bad Request Error.")
        elif (status == 500):
            logging.error("GoodWe SEMS API returned a Server Error.")
            Domoticz.Error("GoodWe SEMS API returned a Server Error.")
        else:
            logging.error("GoodWe SEMS API returned a status: " + str(status))
            Domoticz.Error("GoodWe SEMS API returned a status: " + str(status))

    def onCommand(self, Unit, Command, Level, Hue):
        logging.debug("onCommand called for Unit " + str(Unit) + ": Parameter '" + str(Command) + "', Level: " + str(Level))

    def onDisconnect(self, Connection):
        logging.debug("onDisconnect called for connection to: " + Connection.Address + ":" + Connection.Port)
        self.httpConn = None

    def onHeartbeat(self):
        if self.httpConn is not None and (self.httpConn.Connecting() or self.httpConn.Connected()) and not self.devicesUpdated:
            logging.debug("onHeartbeat called, Connection is alive.")
        elif len(Parameters["Mode1"]) == 0:
            Domoticz.Error("No Power Station ID provided, exiting")
            logging.error("No Power Station ID provided, exiting")
            return
        else:
            self.runAgain = self.runAgain - 1
            if self.runAgain <= 0:

                logging.debug("onHeartbeat called, starting device update.")
                self.startDeviceUpdateV2()

                self.runAgain = int(Parameters["Mode2"])
            # else:
                # logging.debug("onHeartbeat called, run again in " + str(self.runAgain) + " heartbeats.")

global _plugin
_plugin = GoodWeSEMSPlugin()

def calculateNewEnergy(Device, Unit, inputPower):
    try:
        #read power currently on display (comes from previous update) in Watt and energy counter uptill now in Wh
        previousPower,currentCount = Devices[Device].Units[Unit].sValue.split(";") 
    except:
        #in case no values there, just assume zero
        previousPower = 0 #Watt
        currentCount = 0 #Wh
    dt_format = "%Y-%m-%d %H:%M:%S"
    dt_string = Devices[Device].Units[Unit].LastUpdate
    lastUpdateDT = datetime.fromtimestamp(time.mktime(time.strptime(dt_string, dt_format)))
    elapsedTime = datetime.now() - lastUpdateDT
    logging.debug("Test power, previousPower: {}, last update: {:%Y-%m-%d %H:%M}, elapsedTime: {}, elapsedSeconds: {:6.2f}".format(previousPower, lastUpdateDT, elapsedTime, elapsedTime.total_seconds()))
    
    #average current and previous power (Watt) and multiply by elapsed time (hour) to get Watt hour
    previousPower = str(previousPower).replace("w","").replace("W","")
    newCount = round(((float(previousPower) + inputPower ) / 2) * elapsedTime.total_seconds()/3600,2)
    newCounter = newCount + float(currentCount) #add the amount of energy since last update to the already logged energy
    logging.debug("Test power, previousPower: {}, currentCount: {:6.2f}, newCounter: {:6.2f}, added: {:6.2f}".format(previousPower, float(currentCount), newCounter, newCount))
    return newCounter



def onStart():
    global _plugin
    _plugin.onStart()

def onStop():
    global _plugin
    _plugin.onStop()

def onConnect(Connection, Status, Description):
    global _plugin
    _plugin.onConnect(Connection, Status, Description)

def onMessage(Connection, Data):
    global _plugin
    _plugin.onMessage(Connection, Data)

def onCommand(Unit, Command, Level, Hue):
    global _plugin
    _plugin.onCommand(Unit, Command, Level, Hue)

def onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile):
    global _plugin
    _plugin.onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile)

def onDisconnect(Connection):
    global _plugin
    _plugin.onDisconnect(Connection)

def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()

# Generic helper functions
def LogMessage(Message):
    if Parameters["Mode6"] == "File":
        f = open(Parameters["HomeFolder"] + "http.html", "w")
        f.write(Message)
        f.close()
        Domoticz.Log("File written")
        logging.info("File written")

def DumpConfigToLog():
    Domoticz.Debug("Parameters count: " + str(len(Parameters)))
    for x in Parameters:
        if Parameters[x] != "":
            Domoticz.Debug("Parameter: '" + x + "':'" + str(Parameters[x]) + "'")
    Domoticz.Debug("Device count: " + str(len(Devices)))
    for DeviceName in Devices:
        Device = Devices[DeviceName]
        Domoticz.Debug("Device:       '" + str(Device) + "'")
        for UnitNo in Device.Units:
            Unit = Device.Units[UnitNo]
            Domoticz.Debug(" - Unit:       '" + str(Unit) + "'")

    return

def DumpHTTPResponseToLog(httpDict):
    if isinstance(httpDict, dict):
        logging.debug("HTTP Details (" + str(len(httpDict)) + "):")
        for x in httpDict:
            if isinstance(httpDict[x], dict):
                logging.debug("--->'" + x + " (" + str(len(httpDict[x])) + "):")
                for y in httpDict[x]:
                    logging.debug("------->'" + y + "':'" + str(httpDict[x][y]) + "'")
            else:
                logging.debug("--->'" + x + "':'" + str(httpDict[x]) + "'")

def UpdateDevice(Device, Unit, nValue, sValue, AlwaysUpdate=False):
    # Make sure that the Domoticz device still exists (they can be deleted) before updating it
    if (Device in Devices):
        logging.debug("Updating device '"+Devices[Device].Units[Unit].Name+ "' with current sValue '"+Devices[Device].Units[Unit].sValue+"' to '" +sValue+"'")
        if (Devices[Device].Units[Unit].nValue != nValue) or (Devices[Device].Units[Unit].sValue != sValue):
            try:
                Devices[Device].Units[Unit].nValue = nValue
                Devices[Device].Units[Unit].sValue = sValue
                Devices[Device].Units[Unit].Update()
                
                logging.debug("Update "+str(nValue)+":'"+str(sValue)+"' ("+Devices[Device].Units[Unit].Name+")")
            except:
                Domoticz.Error("Update of device failed: "+str(Unit)+"!")
                logging.error("Update of device failed: "+str(Unit)+"!")
    return
