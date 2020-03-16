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
"""
<plugin key="GoodWeSEMS" name="GoodWe solar inverter via SEMS API" version="1.2.3" author="dylian94">
    <description>
        <h2>GoodWe inverter (via SEMS portal)</h2>
        <p>This plugin uses the GoodWe SEMS api to retrieve the status information of your GoodWe inverter.</p>
        <h3>Devices</h3>
        <ul style="list-style-type:square">
            <li>temperature - Inverter temperature (Celcius)</li>
            <li>state - operational state of the inverter</li>
            <li>power - Current and total output power (Watts)</li>
            <li>current - Output current (ampere)</li>
            <li>voltage - Output Voltage</li>
            <li>frequency - Output frquency [Hz]</li>
            <li>inputs - Power/Current/Voltage per input string</li>
        </ul>
        <h3>Configuration</h3>
        <ul>
            <li>Register your inverter at GoodWe SEMS portal (if not done already): <a href="https://www.semsportal.com">https://www.semsportal.com</a></li>
            <li>Choose one of the following options:</li>
            <ol type="a">
                <li>If you want all of your stations added to Domoticz you only have to enter your login information below</li>
                <li>If you want to add one specific station to Domoticz follow the following steps:</li>
                <ol>
                    <li>Login to your account on: <a href="https://www.semsportal.com">www.semsportal.com</a></li>
                    <li>Go to the plant status page for the station you want to add to Domoticz</li>
                    <li>Get the station ID from the URL, this is the sequence of characters after: https://www.semsportal.com/PowerStation/PowerStatusSnMin/</li>
                    <li>Add the station ID to the hardware configuration</li>
                </ol>
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
        <param field="Mode1" label="Power Station ID (Optional)" width="300px"/>
        <param field="Mode2" label="Refresh interval" width="75px">
            <options>
                <option label="10s" value="1"/>
                <option label="30s" value="3"/>
                <option label="1m" value="6"/>
                <option label="5m" value="30" default="true"/>
                <option label="10m" value="60"/>
                <option label="15m" value="90"/>
            </options>
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
import Domoticz
from GoodWe import GoodWe
from GoodWe import PowerStation

class GoodWeSEMSPlugin:
    httpConn = None
    runAgain = 6
    devicesUpdated = False
    goodWeInverter = None
    
    baseDeviceIndex = 0
    maxDeviceIndex = 0

    # inverterTemperatureUnit = 1
    # inverterStateUnit = 9
    # outputCurrentUnit = 2
    # outputVoltageUnit = 3
    # outputPowerUnit = 4
    # inputVoltage1Unit = 5
    # inputAmps1Unit = 6
    # inputPower1Unit = 14
    # inputPower2Unit = 15
    # inputPower3Unit = 16
    # inputPower4Unit = 17
    # inputVoltage2Unit = 7
    # inputVoltage3Unit = 10
    # inputVoltage4Unit = 12
    # inputAmps2Unit = 8
    # inputAmps3Unit = 11
    # inputAmps4Unit = 13
        

    def __init__(self):
        return

    def apiConnection(self):
        if Parameters["Port"] == "443":
            return Domoticz.Connection(Name="SEMS Portal API", Transport="TCP/IP", Protocol="HTTPS",
                                       Address=Parameters["Address"], Port=Parameters["Port"])
        else:
            return Domoticz.Connection(Name="SEMS Portal API", Transport="TCP/IP", Protocol="HTTP",
                                       Address=Parameters["Address"], Port=Parameters["Port"])

    def startDeviceUpdate(self, Connection):
        Domoticz.Debug("startDeviceUpdate, token availability: '" + str(self.goodWeInverter.tokenAvailable)+ "'")
        if not self.goodWeInverter.tokenAvailable:
            self.goodWeInverter.powerStationList = {}
            self.goodWeInverter.powerStationIndex = 0
            self.devicesUpdated = False
            Connection.Send(self.goodWeInverter.tokenRequest(Parameters["Username"], Parameters["Password"]))
        else:
            if self.goodWeInverter.numInverters > 0:
                Connection.Send(self.goodWeInverter.stationDataRequest())
            else:
                Domoticz.Log("request device update but no inverters found.")
                self.httpConn.Disconnect()
                self.httpConn = None


    def onStart(self):
        if Parameters["Mode6"] == "Verbose":
            Domoticz.Debugging(1)
            DumpConfigToLog()
        if Parameters["Mode6"] == "Debug":
            Domoticz.Debugging(2)
            DumpConfigToLog()

        self.goodWeInverter = GoodWe(Parameters["Address"], Parameters["Port"])
        self.runAgain = int(Parameters["Mode2"])

        self.httpConn = self.apiConnection()
        self.httpConn.Connect()

    def onStop(self):
        Domoticz.Log("onStop - Plugin is stopping.")

    def onConnect(self, Connection, Status, Description):
        Domoticz.Debug("onConnect: Status: '" + str(Status) + "', Description: '" + Description + "'")
        if (Status == 0):
            Domoticz.Debug("Connected to SEMS portal API successfully.")
            self.startDeviceUpdate(Connection)
        else:
            Domoticz.Log("Failed to connect (" + str(Status) + ") to: " + Parameters["Address"] + ":" + Parameters[
                "Port"] + " with error: " + Description)

    def onMessage(self, Connection, Data):
        responseText = Data["Data"].decode("utf-8", "ignore")
        status = int(Data["Status"])

        if status == 200:
            apiRresponse = json.loads(responseText)
            apiUrl = apiRresponse["components"]["api"]
            apiData = apiRresponse["data"]

            if "api/v2/Common/CrossLogin" in apiUrl:
                Domoticz.Debug("message received: CrossLogin")
                if apiData == 'Null':
                    Domoticz.Log("SEMS API Token not received")
                    self.goodWeInverter.tokenAvailable = False
                    self.httpConn.Disconnect()
                    #self.httpConn = None
                else:
                    Domoticz.Debug("message apiData: '" + str(apiData) + "'")
                    self.goodWeInverter.token = apiData
                    Domoticz.Debug("SEMS API Token: " + json.dumps(self.goodWeInverter.token))
                    self.goodWeInverter.tokenAvailable = True
                    #request list of stations on this account
                    Connection.Send(self.goodWeInverter.stationListRequest())

            elif "/api/v2/HistoryData/QueryPowerStationByHistory" in apiUrl:
                Domoticz.Debug("message received: QueryPowerStationByHistory")
                if apiData is None or len(apiData)==0:
                    Domoticz.Log("Power station history not received")
                    self.httpConn.Disconnect()
                    #self.httpConn = None
                else:
                    Domoticz.Debug("message apiData: '" + str(apiData) + "'")
                    for stations in apiData["list"]:
                        for data in stations:
                            Domoticz.Debug("station element: '"+ str(data) + "', value: '" + str(stations[data]) +"'")
                    for key, station in enumerate(apiData["list"]):
                        if len(Parameters["Mode1"]) <= 0 or (len(Parameters["Mode1"]) > 0 and station["id"] == Parameters["Mode1"]):
                            #add all found stations if no ID entered, else only log the one that matches the ID
                            self.goodWeInverter.createStation(key, station)
                            Domoticz.Log("Station found: " + station["id"])

                    Connection.Send(self.goodWeInverter.stationDataRequest())

            elif "api/v2/PowerStation/GetMonitorDetailByPowerstationId" in apiUrl:
                Domoticz.Debug("message received: GetMonitorDetailByPowerstationId")
                #Domoticz.Debug("message: '" + apiData + "'")
                if apiData is None or len(apiData) == 0:
                    Domoticz.Error("No station data received from GoodWe SEMS API (Station ID: " + str(self.goodWeInverter.powerStationList[
                        self.goodWeInverter.powerStationIndex]) + ")")
                    self.goodWeInverter.tokenAvailable = False
                else:
                    #Domoticz.Debug("message apiData: '" + str(apiData) + "'")
                    Domoticz.Log("Station data received from GoodWe SEMS API ('" + str(self.goodWeInverter.powerStationList[
                        self.goodWeInverter.powerStationIndex]) + "', index : '" + str(self.goodWeInverter.powerStationIndex)+ "')")
                    theStation = self.goodWeInverter.powerStationList[self.goodWeInverter.powerStationIndex]

                    for inverter in apiData["inverter"]:
                        Domoticz.Debug("inverter found with SN: '" + inverter["sn"] + "'")
                        if inverter["sn"] in theStation.inverters:
                            theStation.inverters[inverter["sn"]].createDevices(Devices)
                            #invertFull = inverter["invert_full"]
                            #Domoticz.Debug("found in inverter: '" + str(inverter) + "'")
                            #Domoticz.Debug("found in inverter full: '" + str(invertFull) + "'")
                            # for data in inverter:
                                # Domoticz.Debug("data in inverter: '" + str(data) + "', value '" + str(inverter[data]) + "'")
                            Domoticz.Debug("Details d in inverter: '" + str(inverter['d']) + "'")
                            
                            theInverter = theStation.inverters[inverter["sn"]]

                            if len(inverter['fault_message']) > 0:
                                Domoticz.Log("Fault message from GoodWe inverter (SN: " + inverter["sn"] + "): '" + str(inverter['fault_message']) + "'")
                            Domoticz.Log("Status of GoodWe inverter (SN: " + inverter["sn"] + "): '" + self.goodWeInverter.INVERTER_STATE[inverter["status"]] + "'")
                            Devices[theInverter.inverterStateUnit].Update(nValue=inverter["status"]+1, sValue=str((inverter["status"]+2)*10))
                            if self.goodWeInverter.INVERTER_STATE[inverter["status"]] == 'generating':
                                Domoticz.Debug("inverter generating, log temp")
                                UpdateDevice(theInverter.inverterTemperatureUnit, 0, str(inverter["tempperature"]))
                                UpdateDevice(theInverter.outputFreq1Unit, 0, str(inverter["d"]["fac1"]))

                            UpdateDevice(theInverter.outputCurrentUnit, 0, str(inverter["output_current"]), AlwaysUpdate=True)
                            UpdateDevice(theInverter.outputVoltageUnit, 0, str(inverter["output_voltage"]), AlwaysUpdate=True)
                            UpdateDevice(theInverter.outputPowerUnit, 0, str(inverter["output_power"]) + ";" + str(inverter["etotal"] * 1000), AlwaysUpdate=True)
                            inputVoltage,inputAmps = inverter["pv_input_1"].split('/')
                            inputPower = (float(inputVoltage[:-1])) * (float(inputAmps[:-1]))
                            #Domoticz.Debug("power calc = V: '"+inputVoltage[:-1]+"', A: '"+inputAmps[:-1]+"', power: W: '" + str(inputPower) + "'")
                            UpdateDevice(theInverter.inputVoltage1Unit, 0, inputVoltage, AlwaysUpdate=True)
                            UpdateDevice(theInverter.inputAmps1Unit, 0, inputAmps, AlwaysUpdate=True)
                            UpdateDevice(theInverter.inputPower1Unit, 0, str(inputPower) + ";0", AlwaysUpdate=True)
                            if "pv_input_2" in inverter:
                                Domoticz.Debug("Second string found")
                                inputVoltage,inputAmps = inverter["pv_input_2"].split('/')
                                UpdateDevice(theInverter.inputVoltage2Unit, 0, inputVoltage, AlwaysUpdate=True)
                                UpdateDevice(theInverter.inputAmps2Unit, 0, inputAmps, AlwaysUpdate=True)
                                inputPower = (float(inputVoltage[:-1])) * (float(inputAmps[:-1]))
                                UpdateDevice(theInverter.inputPower2Unit, 0, str(inputPower) + ";0", AlwaysUpdate=True)
                            if "pv_input_3" in inverter:
                                Domoticz.Debug("Third string found")
                                inputVoltage,inputAmps = inverter["pv_input_3"].split('/')
                                UpdateDevice(theInverter.inputVoltage3Unit, 0, inputVoltage, AlwaysUpdate=True)
                                UpdateDevice(theInverter.inputAmps3Unit, 0, inputAmps, AlwaysUpdate=True)
                                inputPower = float(inputVoltage[:-1]) * float(inputAmps[:-1])
                                UpdateDevice(theInverter.inputPower3Unit, 0, str(inputPower) + ";0", AlwaysUpdate=True)
                            if "pv_input_4" in inverter:
                                Domoticz.Debug("Fourth string found")
                                inputVoltage,inputAmps = inverter["pv_input_4"].split('/')
                                UpdateDevice(theInverter.inputVoltage4Unit, 0, inputVoltage, AlwaysUpdate=True)
                                UpdateDevice(theInverter.inputAmps4Unit, 0, inputAmps, AlwaysUpdate=True)
                                inputPower = float(inputVoltage[:-1]) * float(inputAmps[:-1])
                                UpdateDevice(theInverter.inputPower4Unit, 0, str(inputPower) + ";0", AlwaysUpdate=True)
                        else:
                            Domoticz.Log("Unknown inverter found with S/N: '" + inverter["sn"] +"'.")

                if self.goodWeInverter.powerStationIndex == (len(self.goodWeInverter.powerStationList) - 1):
                    Domoticz.Debug("Last station of list found")
                    if self.runAgain > 2:
                        Domoticz.Log("Next active heartbeat far away, disconnecting and dropping connection.")
                        self.httpConn.Disconnect()
                        #self.httpConn = None

                    #Domoticz.Log("Updated " + str(len(Devices)) + " device(s) for " + str(len(self.goodWeInverter.powerStationList)) + " station(s) with " + str(int(self.baseDeviceIndex / self.maxDeviceIndex)) + " inverter(s)")
                    self.devicesUpdated = True
                else:
                    Domoticz.Debug("Retrieving next station data (ID: " + self.goodWeInverter.powerStationList[self.goodWeInverter.powerStationIndex] + ")")
                    self.baseDeviceIndex += 1
                    Connection.Send(self.goodWeInverter.stationDataRequest())

        elif status == 302:
            Domoticz.Error("GoodWe SEMS API returned a Page Moved Error.")
        elif status == 400:
            Domoticz.Error("GoodWe SEMS API returned a Bad Request Error.")
        elif (status == 500):
            Domoticz.Error("GoodWe SEMS API returned a Server Error.")
        else:
            Domoticz.Error("GoodWe SEMS API returned a status: " + str(status))

    def onCommand(self, Unit, Command, Level, Hue):
        Domoticz.Debug("onCommand called for Unit " + str(Unit) + ": Parameter '" + str(Command) + "', Level: " + str(Level))

    def onDisconnect(self, Connection):
        Domoticz.Debug("onDisconnect called for connection to: " + Connection.Address + ":" + Connection.Port)
        self.httpConn = None

    def onHeartbeat(self):
        if self.httpConn is not None and (self.httpConn.Connecting() or self.httpConn.Connected()) and not self.devicesUpdated:
            Domoticz.Debug("onHeartbeat called, Connection is alive.")
        else:
            self.runAgain = self.runAgain - 1
            if self.runAgain <= 0:

                Domoticz.Debug("onHeartbeat called, starting device update.")
                if self.httpConn is None:
                    self.httpConn = self.apiConnection()

                if not self.httpConn.Connected():
                    self.httpConn.Connect()
                else:
                    self.startDeviceUpdate(self.httpConn)

                self.runAgain = int(Parameters["Mode2"])
            else:
                Domoticz.Debug("onHeartbeat called, run again in " + str(self.runAgain) + " heartbeats.")


global _plugin
_plugin = GoodWeSEMSPlugin()

def UpdateDevice(Unit, nValue, sValue, BatteryLevel=255, AlwaysUpdate=False):
    if Unit not in Devices: return
    if Devices[Unit].nValue != nValue\
        or Devices[Unit].sValue != sValue\
        or Devices[Unit].BatteryLevel != BatteryLevel\
        or AlwaysUpdate == True:

        Devices[Unit].Update(nValue, str(sValue), BatteryLevel=BatteryLevel)

        Domoticz.Debug("Update %s: nValue %s - sValue %s - BatteryLevel %s" % (
            Devices[Unit].Name,
            nValue,
            sValue,
            BatteryLevel))

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


def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            Domoticz.Debug("'" + x + "':'" + str(Parameters[x]) + "'")
    Domoticz.Debug("Device count: " + str(len(Devices)))
    for x in Devices:
        Domoticz.Debug("Device:           " + str(x) + " - " + str(Devices[x]))
        Domoticz.Debug("Device ID:       '" + str(Devices[x].ID) + "'")
        Domoticz.Debug("Device Name:     '" + Devices[x].Name + "'")
        Domoticz.Debug("Device nValue:    " + str(Devices[x].nValue))
        Domoticz.Debug("Device sValue:   '" + Devices[x].sValue + "'")
        Domoticz.Debug("Device LastLevel: " + str(Devices[x].LastLevel))
    return


def DumpHTTPResponseToLog(httpDict):
    if isinstance(httpDict, dict):
        Domoticz.Debug("HTTP Details (" + str(len(httpDict)) + "):")
        for x in httpDict:
            if isinstance(httpDict[x], dict):
                Domoticz.Debug("--->'" + x + " (" + str(len(httpDict[x])) + "):")
                for y in httpDict[x]:
                    Domoticz.Debug("------->'" + y + "':'" + str(httpDict[x][y]) + "'")
            else:
                Domoticz.Debug("--->'" + x + "':'" + str(httpDict[x]) + "'")
