"""Manual test harness for plugin.py

This script creates a minimal fake Domoticz environment and exercises
selected plugin procedures without requiring the full Domoticz host.

Run:
    python manual_test.py
"""

import importlib
import sys
import time
import types
from datetime import datetime, timedelta


class FakeConfiguration(dict):
    def __init__(self, initial=None):
        super().__init__(fakeDomoticz_module.configuration_store)
        if isinstance(initial, dict):
            super().update(initial)

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        fakeDomoticz_module.configuration_store[key] = value


class FakeUnit:
    def __init__(self, Name, DeviceID, Unit, Type=None, Subtype=None, **kwargs):
        self.Name = Name
        self.DeviceID = DeviceID
        self.Unit = Unit
        self.Type = Type
        self.Subtype = Subtype
        self.Options = kwargs.get("Options")
        self.Used = kwargs.get("Used")
        self.Switchtype = kwargs.get("Switchtype")
        self.nValue = 0
        self.sValue = ""
        self.LastUpdate = ""
        self.update_called = 0

    def Create(self):
        plugin_module = sys.modules.get("plugin")
        if plugin_module is None:
            return
        devices = getattr(plugin_module, "Devices", None)
        if devices is None:
            return
        if self.DeviceID not in devices:
            devices[self.DeviceID] = FakeDevice(self.DeviceID)
        devices[self.DeviceID].Units[self.Unit] = self
        print(f"[fakeDomoticz] Created unit {self.Unit} for device {self.DeviceID}")

    def Update(self):
        self.update_called += 1
        self.LastUpdate = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(
            f"[fakeDomoticz] Updated device {self.DeviceID} unit {self.Unit}: nValue={self.nValue}, sValue={self.sValue}"
        )


class FakeDevice:
    def __init__(self, DeviceID):
        self.DeviceID = DeviceID
        self.Units = {}

    def __repr__(self):
        return f"<FakeDevice {self.DeviceID}>"


class FakeDomoticzClass:
    def Log(self, message):
        print(f"[Domoticz.Log] {message}")

    def Status(self, message):
        print(f"[Domoticz.Status] {message}")

    def Error(self, message):
        print(f"[Domoticz.Error] {message}")

    def Debug(self, message):
        print(f"[Domoticz.Debug] {message}")

    def Debugging(self, level):
        print(f"[Domoticz.Debugging] level={level}")

    def Configuration(self, config=None):
        return FakeConfiguration(config)

    def Device(self, DeviceID=None, Name=None, **kwargs):
        return FakeDevice(DeviceID)

    def Unit(self, Name=None, DeviceID=None, Unit=None, Type=None, Subtype=None, **kwargs):
        return FakeUnit(Name, DeviceID, Unit, Type=Type, Subtype=Subtype, **kwargs)


def install_fake_domoticz():
    global fakeDomoticz_module

    fakeDomoticz_module = types.ModuleType("fakeDomoticz")
    fakeDomoticz_module.configuration_store = {}
    fakeDomoticz_module.Log = lambda message: print(f"[fakeDomoticz.Log] {message}")
    fakeDomoticz_module.Status = lambda message: print(f"[fakeDomoticz.Status] {message}")
    fakeDomoticz_module.Error = lambda message: print(f"[fakeDomoticz.Error] {message}")
    fakeDomoticz_module.Debug = lambda message: print(f"[fakeDomoticz.Debug] {message}")
    fakeDomoticz_module.Debugging = lambda level: print(f"[fakeDomoticz.Debugging] level={level}")
    fakeDomoticz_module.Configuration = FakeConfiguration
    fakeDomoticz_module.Device = FakeDevice
    fakeDomoticz_module.Unit = FakeUnit
    fakeDomoticz_module.Domoticz = FakeDomoticzClass
    sys.modules["fakeDomoticz"] = fakeDomoticz_module

    if "requests" not in sys.modules:
        try:
            import requests  # noqa: F401
        except ImportError:
            requests_module = types.ModuleType("requests")

            class RequestException(Exception):
                pass

            def post(*args, **kwargs):
                raise RequestException("requests is not installed")

            requests_module.RequestException = RequestException
            requests_module.post = post
            sys.modules["requests"] = requests_module


def load_plugin_module():
    install_fake_domoticz()
    if "plugin" in sys.modules:
        del sys.modules["plugin"]
    return importlib.import_module("plugin")


def setup_plugin_environment(plugin_module):
    plugin_module.Devices = {}
    plugin_module.Parameters = {
        "Name": "ManualTest",
        "Mode6": "Normal",
        "Mode1": "test-powerstation-id",
        "Mode2": "30",
        "Mode4": "No",
        "Version": "5.0.0",
        "Address": "eu.semsportal.com",
        "Port": "443",
        "Username": "test@example.com",
        "Password": "password",
    }
    plugin_module.Domoticz = plugin_module.Domoticz


def test_update_device(plugin_module):
    print("\nRunning test_update_device()")
    plugin_module.Devices = {"sn_test": FakeDevice("sn_test")}
    unit = FakeUnit("Output Power", "sn_test", 4)
    plugin_module.Devices["sn_test"].Units[4] = unit

    plugin_module.UpdateDevice("sn_test", 4, 1, "123;456")
    assert unit.nValue == 1, "nValue should update to 1"
    assert unit.sValue == "123;456", "sValue should update"
    assert unit.update_called == 1, "Update should be called once"

    plugin_module.UpdateDevice("sn_test", 4, 1, "123;456")
    assert unit.update_called == 1, "No update should be called when values are unchanged"

    plugin_module.UpdateDevice("sn_test", 4, 1, "123;456", AlwaysUpdate=True)
    assert unit.update_called == 2, "AlwaysUpdate should force a second update"
    print("test_update_device passed")


def test_calculate_new_energy(plugin_module):
    print("\nRunning test_calculate_new_energy()")
    plugin_module.Devices = {"sn_energy": FakeDevice("sn_energy")}
    unit = FakeUnit("Input Power 1", "sn_energy", plugin_module._plugin.inputPower1Unit)
    unit.sValue = "10;100"
    unit.LastUpdate = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    plugin_module.Devices["sn_energy"].Units[plugin_module._plugin.inputPower1Unit] = unit

    new_counter = plugin_module.calculateNewEnergy(
        "sn_energy", plugin_module._plugin.inputPower1Unit, 20.0
    )
    assert abs(new_counter - 115.0) < 0.5, f"Expected about 115.0, got {new_counter}"
    print("test_calculate_new_energy passed")


def test_create_devices(plugin_module):
    print("\nRunning test_create_devices()")
    plugin_module.Devices = {}
    plugin_module._plugin.createDevices("sn_device")
    assert "sn_device" in plugin_module.Devices, "Device should be created"
    created_units = plugin_module.Devices["sn_device"].Units
    assert plugin_module._plugin.inverterTemperatureUnit in created_units, "Temperature unit must be created"
    assert plugin_module._plugin.outputPowerUnit in created_units, "Output power unit must be created"
    print(f"Created {len(created_units)} units for serial sn_device")
    print("test_create_devices passed")


def test_check_version(plugin_module):
    print("\nRunning test_check_version()")
    fakeDomoticz_module.configuration_store.clear()
    fakeDomoticz_module.configuration_store["plugin version"] = "4.0.0"
    fakeDomoticz_module.configuration_store["MajorVersion"] = "4"
    fakeDomoticz_module.configuration_store["MinorVersion"] = "0"
    fakeDomoticz_module.configuration_store["patchVersion"] = "0"

    plugin_module.Devices = {}
    result = plugin_module._plugin.checkVersion("5.0.0")
    assert result is True, "checkVersion should return True when upgrade path is allowed"
    assert fakeDomoticz_module.configuration_store.get("plugin version") == "5.0.0"
    print("test_check_version passed")


def main():
    print("Starting manual test harness for plugin.py")
    plugin_module = load_plugin_module()
    setup_plugin_environment(plugin_module)

    tests = [
        test_update_device,
        test_calculate_new_energy,
        test_create_devices,
        test_check_version,
    ]

    failures = 0
    for test in tests:
        try:
            test(plugin_module)
        except AssertionError as err:
            failures += 1
            print(f"{test.__name__} failed: {err}")
        except Exception as exc:
            failures += 1
            print(f"{test.__name__} raised an unexpected exception: {exc}")

    if failures:
        print(f"\nManual test completed with {failures} failure(s).")
        sys.exit(1)
    print("\nManual test completed successfully.")


if __name__ == "__main__":
    main()
