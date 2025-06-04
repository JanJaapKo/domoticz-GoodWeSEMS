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
<plugin key="GoodWeSEMS" name="GoodWe solar inverter via SEMS API" version="4.1.0" author="Jan-Jaap Kostelijk">
    <description>
        <h2>GoodWe inverter (via SEMS portal)</h2>
        <p>This plugin uses the GoodWe SEMS api to retrieve the status information of your GoodWe inverter.</p>
        <p>Version: 4.0.1</p>
        <p>Important upgrade note: <a href="https://github.com/JanJaapKo/domoticz-GoodWeSEMS/wiki">plugin wiki</a></p>
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
                <option label="10s" value="1"/>
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
try:
	import DomoticzEx as Domoticz
	debug = False
except ImportError:
    from fakeDomoticz import *
    from fakeDomoticz import Domoticz
    Domoticz = Domoticz()
    debug = True
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
        self.inverterStateCommand = 19 + startNum
        self.enabled = False
        return

    def apiConnection(self):
        if Parameters["Port"] == "443":
            return Domoticz.Connection(Name="SEMS Portal API", Transport="TCP/IP", Protocol="HTTPS",
                                       Address=Parameters["Address"], Port=Parameters["Port"])
        else:
            return Domoticz.Connection(Name="SEMS Portal API", Transport="TCP/IP", Protocol="HTTP",
                                       Address=Parameters["Address"], Port=Parameters["Port"])

    def establishToken(self):
        logging.debug("establishToken, token availability: '" + str(self.goodWeAccount.tokenAvailable)+ "'")
        if not self.goodWeAccount.tokenAvailable:
            self.goodWeAccount.powerStationList = {}
            self.goodWeAccount.powerStationIndex = 0
            self.devicesUpdated = False
            try:
                self.goodWeAccount.tokenRequest()
                return True
            except (exceptions.GoodweException, exceptions.FailureWithMessage, exceptions.FailureWithoutMessage) as exp:
                logging.error("Failed to request data: " + str(exp))
                Domoticz.Error("Failed to request data: " + str(exp))
                return False

    def getDeviceData(self):            
        if self.goodWeAccount.tokenAvailable:
            try:
                DeviceData = self.goodWeAccount.stationDataRequestV2(Parameters["Mode1"])
            except (exceptions.TooManyRetries, exceptions.FailureWithErrorCode, exceptions.FailureWithoutErrorCode) as exp:
                logging.error("Failed to request data: " + str(exp))
                Domoticz.Error("Failed to request data: " + str(exp))
                return None
            return DeviceData

    def startDeviceUpdateV2(self):
        if not self.establishToken(): return
        DeviceData = self.getDeviceData()
        if DeviceData == None:
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
        logging.debug("creating units for device with serial number: "+ serialNumber)
        thisDevice = Domoticz.Device(DeviceID=serialNumber) #use serial number as identifier for Domoticz.Device instance
        #numDevs = len(Devices[serialNumber].Units)
        if serialNumber not in Devices or self.inverterTemperatureUnit not in Devices[serialNumber].Units:
            Domoticz.Unit(Name="Inverter temperature (SN: " + serialNumber + ")", DeviceID=serialNumber,
                            Unit=(self.inverterTemperatureUnit), Type=80, Subtype=5).Create()
        #if self.outputCurrentUnit not in Devices:
        if serialNumber not in Devices or self.outputCurrentUnit not in Devices[serialNumber].Units:
            Domoticz.Unit(Name="Inverter output current (SN: " + serialNumber + ")", DeviceID=serialNumber,
                            Unit=(self.outputCurrentUnit), Type=243, Subtype=23).Create()
        if serialNumber not in Devices or self.outputVoltageUnit not in Devices[serialNumber].Units:
            Domoticz.Unit(Name="Inverter output voltage (SN: " + serialNumber + ")", DeviceID=serialNumber,
                            Unit=(self.outputVoltageUnit), Type=243, Subtype=8).Create()
        if serialNumber not in Devices or self.outputPowerUnit not in Devices[serialNumber].Units:
            Domoticz.Unit(Name="Inverter output power (SN: " + serialNumber + ")", DeviceID=serialNumber,
                            Unit=(self.outputPowerUnit), Type=243, Subtype=29,
                            Switchtype=4, Used=1).Create()
                            
        if serialNumber not in Devices or self.inverterStateUnit not in Devices[serialNumber].Units:
            Options = {"LevelActions": "|||",
                  "LevelNames": "|Offline|Waiting|Generating|Error",
                  "LevelOffHidden": "true",
                  "SelectorStyle": "1"}
            Domoticz.Unit(Name="Inverter state (SN: " + serialNumber + ")",
                            Unit=(self.inverterStateUnit), TypeName="Selector Switch", Image=1,
                            Options=Options, Used=1, DeviceID=serialNumber).Create()
                            
        if serialNumber not in Devices or self.inputVoltage1Unit not in Devices[serialNumber].Units:
            Domoticz.Unit(Name="Inverter input 1 voltage (SN: " + serialNumber + ")",
                            Unit=(self.inputVoltage1Unit), Type=243, Subtype=8, 
                            DeviceID=serialNumber).Create()
        if serialNumber not in Devices or self.inputAmps1Unit not in Devices[serialNumber].Units:
            Domoticz.Unit(Name="Inverter input 1 Current (SN: " + serialNumber + ")",
                            Unit=(self.inputAmps1Unit), Type=243, Subtype=23,
                            Switchtype=4, Used=0, DeviceID=serialNumber).Create()
        if serialNumber not in Devices or self.inputPower1Unit not in Devices[serialNumber].Units:
            Domoticz.Unit(Name="Inverter input 1 power (SN: " + serialNumber + ")",
                            Unit=(self.inputPower1Unit), Type=243, Subtype=29,
                            Switchtype=4, Used=1, DeviceID=serialNumber).Create()
        if serialNumber not in Devices or self.inputVoltage2Unit not in Devices[serialNumber].Units:
            Domoticz.Unit(Name="Inverter input 2 voltage (SN: " + serialNumber + ")",
                            Unit=(self.inputVoltage2Unit), Type=243, Subtype=8, Used=0, 
                            DeviceID=serialNumber).Create()
        #input string 2.. 4 are optional. Set devices to not-used
        if serialNumber not in Devices or self.inputAmps2Unit not in Devices[serialNumber].Units:
            Domoticz.Unit(Name="Inverter input 2 Current (SN: " + serialNumber + ")",
                            Unit=(self.inputAmps2Unit), Type=243, Subtype=23,
                            Switchtype=4, Used=0, DeviceID=serialNumber).Create()
        if serialNumber not in Devices or self.inputVoltage3Unit not in Devices[serialNumber].Units:
            Domoticz.Unit(Name="Inverter input 3 voltage (SN: " + serialNumber + ")",
                            Unit=(self.inputVoltage3Unit), Type=243, Subtype=8, Used=0, 
                            DeviceID=serialNumber).Create()
        if serialNumber not in Devices or self.inputAmps3Unit not in Devices[serialNumber].Units:
            Domoticz.Unit(Name="Inverter input 3 Current (SN: " + serialNumber + ")",
                            Unit=(self.inputAmps3Unit), Type=243, Subtype=23,
                            Switchtype=4, Used=0, DeviceID=serialNumber).Create()
        if serialNumber not in Devices or self.inputVoltage4Unit not in Devices[serialNumber].Units:
            Domoticz.Unit(Name="Inverter input 4 voltage (SN: " + serialNumber + ")",
                            Unit=(self.inputVoltage4Unit), Type=243, Subtype=8, Used=0, 
                            DeviceID=serialNumber).Create()
        if serialNumber not in Devices or self.inputAmps4Unit not in Devices[serialNumber].Units:
            Domoticz.Unit(Name="Inverter input 4 Current (SN: " + serialNumber + ")",
                            Unit=(self.inputAmps4Unit), Type=243, Subtype=23,
                            Switchtype=4, Used=0, DeviceID=serialNumber).Create()
        if serialNumber not in Devices or self.inputPower2Unit not in Devices[serialNumber].Units:
            Domoticz.Unit(Name="Inverter input 2 power (SN: " + serialNumber + ")",
                            Unit=(self.inputPower2Unit), Type=243, Subtype=29,
                            Switchtype=4, Used=0, DeviceID=serialNumber).Create()
        if serialNumber not in Devices or self.inputPower3Unit not in Devices[serialNumber].Units:
            Domoticz.Unit(Name="Inverter input 3 power (SN: " + serialNumber + ")",
                            Unit=(self.inputPower3Unit), Type=243, Subtype=29,
                            Switchtype=4, Used=0, DeviceID=serialNumber).Create()
        if serialNumber not in Devices or self.inputPower4Unit not in Devices[serialNumber].Units:
            Domoticz.Unit(Name="Inverter input 4 power (SN: " + serialNumber + ")",
                            Unit=(self.inputPower4Unit), Type=243, Subtype=29,
                            Switchtype=4, Used=0, DeviceID=serialNumber).Create()
        if serialNumber not in Devices or self.outputFreq1Unit not in Devices[serialNumber].Units:
            Domoticz.Unit(Name="Inverter output frequency 1 (SN: " + serialNumber + ")",
                            Unit=(self.outputFreq1Unit), TypeName="Custom",
                            Used=0, DeviceID=serialNumber).Create()
        if serialNumber not in Devices or self.inverterStateCommand not in Devices[serialNumber].Units:

            Options = {"LevelActions": "|||",
                  "LevelNames": "|Reboot|Waiting/off|N/A|Restart",
                  "LevelOffHidden": "true",
                  "SelectorStyle": "1"}
            Domoticz.Unit(Name="Inverter state control (SN: " + serialNumber + ")",
                            Unit=(self.inverterStateCommand), TypeName="Selector Switch", Image=1,
                            Options=Options, Used=0, DeviceID=serialNumber).Create()

        if serialNumber in Devices:
            Domoticz.Debug("Number of Units: " + str(len(Devices[serialNumber].Units)) + ", number of units: " + str(len(Devices[serialNumber].Units)) + ")")
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

        #check upgrading of version needs actions
        self.version = Parameters["Version"]
        self.enabled = self.checkVersion(self.version)
        if not self.enabled:
            return False

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

    def onCommand(self, DeviceID, Unit, Command, Level, Hue):
        logging.debug("onCommand called for Device '" + str(DeviceID) + "', Unit '" + str(Unit) + "': Parameter '" + str(Command) + "', Level: " + str(Level))
        if Unit == self.inverterStateCommand:
            mode = Level / 10
            # self.goodWeAccount.setInverterStatus("54200DSN196R0358","54200DSN196R0358",4)
            return

    def onDisconnect(self, Connection):
        logging.debug("onDisconnect called for connection to: " + Connection.Address + ":" + Connection.Port)
        self.httpConn = None

    def onHeartbeat(self):
        if self.enabled:
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

    def checkVersion(self, version):
        """checks actual version against stored version as 'Ma.Mi.Pa' and checks if updates needed"""
        #read version from stored configuration
        ConfVersion = getConfigItem("plugin version", "0.0.0")
        Domoticz.Log("Starting version: " + version )
        logging.info("Starting version: " + version )
        MaCurrent,MiCurrent,PaCurrent = version.split('.')
        MaConf,MiConf,PaConf = ConfVersion.split('.')
        logging.debug("checking versions: current '{0}', config '{1}'".format(version, ConfVersion))
        can_continue = True
        if int(MaConf) < int(MaCurrent):
            Domoticz.Log("Major version upgrade: {0} -> {1}".format(MaConf,MaCurrent))
            logging.info("Major version upgrade: {0} -> {1}".format(MaConf,MaCurrent))
            #add code to perform MAJOR upgrades
            if int(MaConf) < 4:
                can_continue = self.updateToEx()
        elif int(MiConf) < int(MiCurrent):
            Domoticz.Debug("Minor version upgrade: {0} -> {1}".format(MiConf,MiCurrent))
            logging.debug("Minor version upgrade: {0} -> {1}".format(MiConf,MiCurrent))
            #add code to perform MINOR upgrades
        elif int(PaConf) < int(PaCurrent):
            Domoticz.Debug("Patch version upgrade: {0} -> {1}".format(PaConf,PaCurrent))
            logging.debug("Patch version upgrade: {0} -> {1}".format(PaConf,PaCurrent))
            #add code to perform PATCH upgrades, if any
        if ConfVersion != version and can_continue:
            #store new version info
            self._setVersion(MaCurrent,MiCurrent,PaCurrent)
        return can_continue

    def updateToEx(self):
        """routine to check if we can update to the Domoticz extended plugin framework"""
        if len(Devices)>0:
            Domoticz.Error("Devices are present. Please upgrade them before upgrading to this version!")
            Domoticz.Error("Plugin will now exit but will be enabled on next start")
            self._setVersion("4","0","0")
            return False
        else:
            return True

    def _setVersion(self, major, minor, patch):
        #set configs
        logging.debug("Setting version to {0}.{1}.{2}".format(major, minor, patch))
        setConfigItem(Key="MajorVersion", Value=major)
        setConfigItem(Key="MinorVersion", Value=minor)
        setConfigItem(Key="patchVersion", Value=patch)
        setConfigItem(Key="plugin version", Value="{0}.{1}.{2}".format(major, minor, patch))


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
    if len(dt_string) > 0:
        lastUpdateDT = datetime.fromtimestamp(time.mktime(time.strptime(dt_string, dt_format)))
    else:
        lastUpdateDT = datetime.now()
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

def onCommand(DeviceID, Unit, Command, Level, Color):
    global _plugin
    _plugin.onCommand(DeviceID, Unit, Command, Level, Color)

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
        if (Devices[Device].Units[Unit].nValue != nValue) or (Devices[Device].Units[Unit].sValue != sValue) or AlwaysUpdate:
            #try:
                Devices[Device].Units[Unit].nValue = nValue
                Devices[Device].Units[Unit].sValue = sValue
                Devices[Device].Units[Unit].Update()
                
                logging.debug("Update "+str(nValue)+":'"+str(sValue)+"' ("+Devices[Device].Units[Unit].Name+")")
            # except:
                # Domoticz.Error("Update of device failed: "+str(Unit)+"!")
                # logging.error("Update of device failed: "+str(Unit)+"!")
    return

# Configuration Helpers
def getConfigItem(Key=None, Default={}):
   Value = Default
   try:
       Config = Domoticz.Configuration()
       if (Key != None):
           Value = Config[Key] # only return requested key if there was one
       else:
           Value = Config      # return the whole configuration if no key
   except KeyError:
       Value = Default
   except Exception as inst:
       Domoticz.Error("Domoticz.Configuration read failed: '"+str(inst)+"'")
   return Value
   
def setConfigItem(Key=None, Value=None):
    Config = {}
    if type(Value) not in (str, int, float, bool, bytes, bytearray, list, dict):
        Domoticz.Error("A value is specified of a not allowed type: '" + str(type(Value)) + "'")
        return Config
    try:
       Config = Domoticz.Configuration()
       if (Key != None):
           Config[Key] = Value
       else:
           Config = Value  # set whole configuration if no key specified
       Config = Domoticz.Configuration(Config)
    except Exception as inst:
       Domoticz.Error("Domoticz.Configuration operation failed: '"+str(inst)+"'")
    return Config
