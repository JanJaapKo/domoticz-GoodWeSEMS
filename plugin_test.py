import unittest
from GoodWe import GoodWe
from GoodWe import PowerStation
from GoodWe import Inverter

class InverterTest(unittest.TestCase):
    inverter = None
    inverterApi = None
    powerStation = None
    
    def setUp(self):
        inverterApi = {'sn': '54200DSN196R0358', 'name': 'GW4200D-NS', 'change_num': 0, 'change_type': 0, 'relation_sn': None, 'relation_name': None, 'status': -1}
        self.inverter = Inverter(inverterApi, 1)
        stationId = "a73d66f6-aa49-428e-9f93-bdd781f04b7c"
        self.powerStation = PowerStation(id = stationId)
        
    def test_starting_out(self):
        self.assertEqual(1, 1)
    def test_invSerial(self):
        self.assertEqual(self.inverter.serialNumber, '54200DSN196R0358')
    def test_invType(self):
        self.assertEqual(self.inverter.type, 'GW4200D-NS')
    def test_psID(self):
        self.assertEqual(self.powerStation.id, "a73d66f6-aa49-428e-9f93-bdd781f04b7c")
    def test_psName(self):
        self.assertEqual(self.powerStation.name, "")
    def test_psFreeDev(self):
        self.assertEqual(self.powerStation.firstFreeDeviceNum, 0)

class PowerStationTest(unittest.TestCase):
    inverter = None
    def test_starting_out(self):
        self.assertEqual(1, 1)


def main():
    unittest.main()

if __name__ == "__main__":
    main()