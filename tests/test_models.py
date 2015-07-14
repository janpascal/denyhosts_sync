# denyhosts sync server
# Copyright (C) 2015 Jan-Pascal van Best <janpascal@vanbest.org>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import time

from dh_syncserver import models
from dh_syncserver import controllers 
from dh_syncserver.models import Cracker, Report

from twisted.internet.defer import inlineCallbacks, returnValue

import base

class ModelsTest(base.TestBase):

    @inlineCallbacks
    def test_add_cracker(self):
        cracker_ip = "127.0.0.1"
        now = time.time()
        cracker = Cracker(ip_address=cracker_ip, first_time=now, latest_time=now, total_reports=0, current_reports=0, resiliency=0)
        cracker = yield cracker.save()

        c2 = yield controllers.get_cracker(cracker_ip)
        yield self.assertIsNotNone(c2)
        self.assertEqual(c2.ip_address, cracker.ip_address, "Save and re-fetch cracker from database")
        self.assertEqual(c2.id, cracker.id, "Save and re-fetch cracker from database")
        self.assertEqual(c2.first_time, cracker.first_time, "Save and re-fetch cracker from database")
        self.assertEqual(c2.latest_time, cracker.latest_time, "Save and re-fetch cracker from database")
        self.assertEqual(c2.total_reports, cracker.total_reports, "Save and re-fetch cracker from database")
        self.assertEqual(c2.current_reports, cracker.current_reports, "Save and re-fetch cracker from database")
        self.assertEqual(c2.id, cracker.id, "Save and re-fetch cracker from database")

    @inlineCallbacks
    def test_add_report(self):
        now = time.time()
        yield Cracker(ip_address="192.168.1.1", first_time=now, latest_time=now, total_reports=0, current_reports=0).save()
        c = yield controllers.get_cracker("192.168.1.1")
        yield self.assertIsNotNone(c)
        yield controllers.add_report_to_cracker(c, "127.0.0.1")

        r = yield Report.find(where=["cracker_id=? and ip_address=?",c.id,"127.0.0.1"], limit=1)
        returnValue(self.assertIsNotNone(r, "Added report is in database"))
        
    @inlineCallbacks
    def test_add_multiple_reports(self):
        now = time.time()

        yield Cracker(ip_address="192.168.1.1", first_time=now, latest_time=now, total_reports=0, current_reports=0).save()
        c = yield controllers.get_cracker("192.168.1.1")
        yield self.assertIsNotNone(c)
        yield controllers.add_report_to_cracker(c, "127.0.0.1", now)

        reports = yield Report.find(where=["cracker_id=? and ip_address=?",c.id,"127.0.0.1"])
        self.assertEqual(len(reports), 1, "First added report is in database")

        # Add second report shortly after first
        yield controllers.add_report_to_cracker(c, "127.0.0.1", now+1)
        reports = yield Report.find(where=["cracker_id=? and ip_address=?",c.id,"127.0.0.1"])
        self.assertEqual(len(reports), 1, "Second added report should be ignored")

        # Add second report after 24 hours
        yield controllers.add_report_to_cracker(c, "127.0.0.1", now+24*3600+1)
        reports = yield Report.find(where=["cracker_id=? and ip_address=?",c.id,"127.0.0.1"])
        self.assertEqual(len(reports), 2, "Second report should be added after 24 hours ")

        # Add third report shortly after second, should be ignored
        yield controllers.add_report_to_cracker(c, "127.0.0.1", now+24*3600+10)
        reports = yield Report.find(where=["cracker_id=? and ip_address=?",c.id,"127.0.0.1"])
        self.assertEqual(len(reports), 2, "Third report shortly after second should be ignored")

        # Add third report after again 24 hours
        yield controllers.add_report_to_cracker(c, "127.0.0.1", now+2*24*3600+20)
        reports = yield Report.find(where=["cracker_id=? and ip_address=?",c.id,"127.0.0.1"])
        self.assertEqual(len(reports), 3, "Third report after again 24 hours, should be added")

        # Add fourth report 
        time_added = now + 2*24*3600 + 30
        yield controllers.add_report_to_cracker(c, "127.0.0.1", time_added)
        reports = yield Report.find(
            where=["cracker_id=? and ip_address=?",c.id,"127.0.0.1"], 
            orderby='latest_report_time asc')
        self.assertEqual(len(reports), 3, "Fourth report, should be merged")
        self.assertEqual(reports[-1].latest_report_time, time_added, "Latest report time should be updated")

        self.assertEquals(c.current_reports, 1, "Only one unique reporter should be counted")
        self.assertEquals(c.total_reports, 6, "Cracker reported six timed in total")

        # Perform maintenance, expire original report
        yield controllers.perform_maintenance(limit = now+1) 
        reports = yield Report.find(where=["cracker_id=? and ip_address=?",c.id,"127.0.0.1"])
        self.assertEqual(len(reports), 2, "Maintenance should remove oldest report")
        yield c.refresh()
        self.assertEqual(c.current_reports, 1, "Maintenance should still leave one unique reporter")

        # Perform maintenance, expire second report
        yield controllers.perform_maintenance(limit = now+24*3600+11) 
        reports = yield Report.find(where=["cracker_id=? and ip_address=?",c.id,"127.0.0.1"])
        self.assertEqual(len(reports), 1, "Maintenance should remove one more report")
        yield c.refresh()
        self.assertEqual(c.current_reports, 1, "Maintenance should still leave one unique reporter")

        # Perform maintenance again, expire last report and cracker
        yield controllers.perform_maintenance(limit = now+2*24*3600+31) 
        reports = yield Report.find(where=["cracker_id=? and ip_address=?",c.id,"127.0.0.1"])
        self.assertEqual(len(reports), 0, "Maintenance should remove last report")
        cracker = yield controllers.get_cracker("192.168.1.1")
        self.assertIsNone(cracker, "Maintenance should remove cracker")

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
