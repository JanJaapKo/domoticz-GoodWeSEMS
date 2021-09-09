Domoticz GoodWe Solar Inverter plugin (SEMS API)
===============================================
This plugin provides information about your GoodWe solar inverter too Domoticz. This plugin has been made by analysing requests made by the GoodWe SEMS Portal website and following the API documentation provided by GoodWe.

This plugin was created by Dylian94 ([/dylian94/domoticz-GoodWeSEMS](https://github.com/dylian94/domoticz-GoodWeSEMS)) but that version is out of maintenance. Additional credits to [Mark Ruys' gw2pvo](https://github.com/markruys/gw2pvo) for getting the API calls right.......

Installation and setup
----------------------
Follow the Domoticz guide on [Using Python Plugins](https://www.domoticz.com/wiki/Using_Python_plugins).

Login to a shell, go to the domoticz plugin directory and clone this repository:
```bash
cd domoticz/plugins
git clone git@github.com:janjaapko/domoticz-GoodWeSEMS.git
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
    - temperature: Inverter temperature (Celcius)
    - power: Current and total output power (Watts)
    - current - Output current (ampere)
    - voltage - Output Voltage
    - frequency - Output frequncy (Hz, first phase)
    - input strings: Voltage, current and power per string

There is a lot more information available trough the GoodWe API if you would like to have a specific feature added to this plugin please submit an issue as indicated in the paragraph above. 

Current limitations
----------------
1. You can only fetch data for 1 powerstation. The field Power Station ID is now mandatory
2. The GoodWE API does not always respond in time, leading to errors like below. This is not a problem, data will be updated on the next try. 
``` 
Error: Zonnepanelen: (Zonnepanelen) RequestException: HTTPSConnectionPool(host='eu.semsportal.com', port=443): Read timed out. (read timeout=10)
Error: Zonnepanelen: (Zonnepanelen) Failed to request data: Failed to call GoodWe API (too many retries)
```
