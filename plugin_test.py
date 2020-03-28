import unittest
from GoodWe import GoodWe
from GoodWe import PowerStation
from GoodWe import Inverter

class BasicInverterTest(unittest.TestCase):
    inverter = None
    inverterApi = None
    
    def setUp(self):
        #inverter API data is part of the GetMonitorDetailByPowerstationId API data
        self.inverterApi = {'sn': 'sn_simple', 'name': 'name_simple', 'change_num': 0, 'change_type': 0, 'relation_sn': None, 'relation_name': None, 'status': -1}
        self.inverter = Inverter(self.inverterApi, 1)
        
    def test_invSerial(self):
        self.assertEqual(self.inverter.serialNumber, 'sn_simple')
    def test_invType(self):
        self.assertEqual(self.inverter.type, 'name_simple')

class PowerStationTest(unittest.TestCase):
    powerStation = None
    powerStationSingle = None
    powerStationDouble = None
    powerStationApiDataSingle = None
    powerStationApiDataDouble = None
    
    def setUp(self):
        print("starting the test")
        
    def test_starting_out(self):
        self.assertEqual(1, 1)

    def test_powerStationId(self):
        stationId = "a73d66f6-aa49-428e-9f93-bdd781f04b7a"
        self.powerStation = PowerStation(id = stationId)
        self.assertEqual(self.powerStation.id, "a73d66f6-aa49-428e-9f93-bdd781f04b7a")
        self.assertEqual(self.powerStation.name, "")
        self.assertEqual(self.powerStation.firstFreeDeviceNum, 0)

    def test_singlePowerStation(self):
        # power station api data is part of the QueryPowerStationByHistory api data
        #this is a single PS
        self.powerStationApiDataSingle = { 'id': 'a73d66f6-aa49-428e-9f93-bdd781f04b7e', 'pw_name': 'pw_name_1', 'pw_address': 'pw_address_1', 'status': 1, 'inverters': [{'sn': 'inverter_SN1', 'name': 'inverter_name1', 'change_num': 0, 'change_type': 0, 'relation_sn': None, 'relation_name': None, 'status': 1}]}
        self.powerStationSingle = PowerStation(stationData = self.powerStationApiDataSingle)
        print("Created power station: '" + str(self.powerStationSingle) + "'")
        self.assertEqual(self.powerStationSingle.id, 'a73d66f6-aa49-428e-9f93-bdd781f04b7e', msg="Single PS ID fail")
        self.assertEqual(self.powerStationSingle.name, 'pw_name_1', msg="Single PS name fail")
        self.assertEqual(self.powerStationSingle.numInverters, 1, msg="Single PS num inv fail: " + str(self.powerStationSingle.numInverters))

    def test_doublePowerStation(self):
        self.powerStationApiDataDouble = { 'id': 'a73d66f6-aa49-428e-9f93-bdd781f04b7d', 'pw_name': 'pw_name_2', 'pw_address': 'pw_address_2', 'status': 1, 'inverters': [{'sn': 'inverter_SN21', 'name': 'inverter_name21', 'change_num': 0, 'change_type': 0, 'relation_sn': None, 'relation_name': None, 'status': 1},{'sn': 'inverter_SN22', 'name': 'inverter_name22', 'change_num': 0, 'change_type': 0, 'relation_sn': None, 'relation_name': None, 'status': 1}]}
        self.powerStationDouble = PowerStation(stationData = self.powerStationApiDataDouble)
        print("Created power station: '" + str(self.powerStationDouble) + "'")
        self.assertEqual(self.powerStationDouble.id, 'a73d66f6-aa49-428e-9f93-bdd781f04b7d', msg="Double PS ID fail")
        self.assertEqual(self.powerStationDouble.name, 'pw_name_2', msg="Double PS name fail")
        self.assertEqual(self.powerStationDouble.numInverters, 2, msg="Double PS num inv fail: " + str(self.powerStationDouble.numInverters))
        
    def tearDown(self):
        print("tearing down the house")
        self.powerStationSingle = None
        self.powerStationDouble = None
        self.powerStation = None

def main():
    unittest.main()

if __name__ == "__main__":
    main()