import time

from dh_syncserver import config
from dh_syncserver import models
from dh_syncserver import controllers 
from dh_syncserver import database
from dh_syncserver.models import Cracker, Report

from twisted.trial import unittest
from twisted.enterprise import adbapi
from twisted.internet.defer import inlineCallbacks, returnValue

from twistar.registry import Registry

class ModelsTest(unittest.TestCase):
    @inlineCallbacks
    def setUp(self):
        Registry.DBPOOL = adbapi.ConnectionPool("sqlite3", "unittest.sqlite")
        Registry.register(models.Cracker, models.Report)
        # Kludge to get evolve_database to work
        config.dbtype = "sqlite3"
        yield database.clean_database()

        now = time.time()
        yield Cracker(ip_address="192.168.1.1", first_time=now, latest_time=now, total_reports=0, current_reports=0).save()
        yield Cracker(ip_address="192.168.1.2", first_time=now, latest_time=now, total_reports=0, current_reports=0).save()

    def test_dummy(self):
        self.assertTrue(True, "Dummy test")

    def _cb(self, cracker):
        print(cracker)
        self.assertFalse(True)

    @inlineCallbacks
    def test_add_cracker(self):
        cracker_ip = "127.0.0.1"
        now = time.time()
        cracker = Cracker(ip_address=cracker_ip, first_time=now, latest_time=now, total_reports=0, current_reports=0)
        cracker = yield cracker.save()

        #c2 = yield Cracker.find(where=['ip_address=?', cracker_ip], limit=1)
        c2 = yield controllers.get_cracker(cracker_ip)
        yield self.assertIsNotNone(c2)
        returnValue(self.assertEqual(c2.ip_address, cracker.ip_address, "Save and re-fetch cracker from database"))

    @inlineCallbacks
    def test_add_report(self):
        #c = yield Cracker.find(where=['ip_address=?', "192.168.1.1"], limit=1)
        c = yield controllers.get_cracker(ip_address)
        yield self.assertIsNotNone(c)
        yield controllers.add_report_to_cracker(c, "127.0.0.1")
        yield c.save()

        r = yield Report.find(where=["cracker_id=? and ip_address=?",c.id,"127.0.0.1"], limit=1)
        returnValue(self.assertIsNotNone(r, "Added report is in database"))
        
