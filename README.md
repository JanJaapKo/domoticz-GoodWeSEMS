Domoticz GoodWe Solar Inverter plugin (SEMS API)
===============================================
This plugin provides information about your GoodWe solar inverter too Domoticz. This plugin has been made by analysing requests made by the GoodWe SEMS Portal website and following the API documentation provided by GoodWe.

This plugin was created by Dylian94 ([/dylian94/domoticz-GoodWeSEMS](https://github.com/dylian94/domoticz-GoodWeSEMS)) but that version is out of maintenance. Additional credits to [Mark Ruys' gw2pvo](https://github.com/markruys/gw2pvo) for getting the API calls right.......


Important update note (v4)
----------------------
Per version 4 (November 2023), I've updated the plugin to the Domoticz Extend Framework, which means the device definition is changed. To make sure that you still have your historical sensor data, please read the [wiki](https://github.com/JanJaapKo/domoticz-GoodWeSEMS/wiki).

Installation and setup
----------------------
Follow the Domoticz guide on [Using Python Plugins](https://www.domoticz.com/wiki/Using_Python_plugins). Check limitations on the bottom of the page. The following Python modules should be installed. Login to a shell:

```
sudo apt-get update
sudo apt-get install python3-requests
```

Then, go to the domoticz plugin directory and clone this repository (eith SSH, requires git account):
```bash
cd domoticz/plugins
git clone git@github.com:janjaapko/domoticz-GoodWeSEMS.git
```

OR

Login to a shell, go to the domoticz plugin directory and clone this repository (with https, requires no git account):
```bash
cd domoticz/plugins
git clone https://github.com/JanJaapKo/domoticz-GoodWeSEMS.git
```

Restart Domoticz server, you can try one of these commands (on Linux):
```bash
sudo systemctl restart domoticz.service
sudo service domoticz.sh restart
```

Open the Domoticz interface and go to: **Setup** > **Hardware**. You can add new Hardware add the bottom, in the list of hardware types choose for: **GoodWe inverter (via SEMS portal)**.

Follow the instructions shown in the form.

Updating
--------
Login to a shell, go to the plugin directory inside the domoticz plugin directory and execute git pull:
```bash
cd domoticz/plugins/domoticz-GoodWeSEMS
git pull
```

Contributing
------------
Even if you do not know how to develop software you can help by using the [GitHub Issues](https://github.com/janjaapko/domoticz-GoodWeSEMS/issues)
for feature request or bug reports. If you DO know how to develop software please help improving this project by submitting pull-requests. Make sure to update and run the included unit tests (```python plugin_test.py```) prior to submitting

Current features
----------------
1. Get all stations for a specific user account
2. Automatically get data for all inverters (for one station)
3. The following devices are added to Domoticz for each inverter:

|Unit	|Description	|Type   |Remark
|---    |---            |---    |---
|1	|(Hardware name) - Inverter temperature (SN: (your S/N))	|LaCrosse TX3   |
|2	|(Hardware name) - Inverter output current (SN: (your S/N))	|Current        |
|3	|(Hardware name) - Inverter output voltage (SN: (your S/N))	|Voltage        |
|4	|(Hardware name) - Inverter output power (SN: (your S/N))	|kWh            | default: used
|5	|(Hardware name) - Inverter input 1 voltage (SN: (your S/N))	|Voltage    |
|6	|(Hardware name) - Inverter input 1 Current (SN: (your S/N))	|Current    |
|7	|(Hardware name) - Inverter input 2 voltage (SN: (your S/N))	|Voltage    |
|8	|(Hardware name) - Inverter input 2 Current (SN: (your S/N))	|Current    |
|9	|(Hardware name) - Inverter state (SN: (your S/N))	|Selector Switch        | default: used
|10	|(Hardware name) - Solar inverter input 3 voltage (SN: (your S/N))	|Voltage|
|11	|(Hardware name) - Solar inverter input 3 Current (SN: (your S/N))	|Current|
|12	|(Hardware name) - Solar inverter input 4 voltage (SN: (your S/N))	|Voltage|
|13	|(Hardware name) - Solar inverter input 4 Current (SN: (your S/N))	|Current|
|14	|(Hardware name) - Inverter input 1 power (SN: (your S/N))	|kWh            | default: used. calculated in plugin
|15	|(Hardware name) - Inverter input 2 power (SN: (your S/N))	|kWh            | calculated in plugin
|16	|(Hardware name) - Inverter input 3 power (SN: (your S/N))	|kWh            | calculated in plugin
|17	|(Hardware name) - Inverter input 4 power (SN: (your S/N))	|kWh            | calculated in plugin
|18	|(Hardware name) - Inverter output frequency 1	|Custom Sensor              |


There is a lot more information available trough the GoodWe API if you would like to have a specific feature added to this plugin please submit an issue as indicated in the paragraph above. 

Current limitations
----------------
1. You can only fetch data for 1 powerstation (which can consist of more than 1 inverter). The field Power Station ID is now mandatory
2. The GoodWE API does not always respond in time, leading to errors like below. This is not a problem, data will be updated on the next try. 
``` 
Error: Zonnepanelen: (Zonnepanelen) RequestException: HTTPSConnectionPool(host='eu.semsportal.com', port=443): Read timed out. (read timeout=10)
Error: Zonnepanelen: (Zonnepanelen) Failed to request data: Failed to call GoodWe API (too many retries)
```
