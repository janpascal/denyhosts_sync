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

from denyhosts_server import models
from denyhosts_server import controllers 
from denyhosts_server import database
from denyhosts_server.models import Cracker, Report

from twisted.internet.defer import inlineCallbacks, returnValue

import base
import logging

class GetNewHostsTest(base.TestBase):

    @inlineCallbacks
    def test_get_qualifying_crackers(self):
        now = time.time()
        c = yield Cracker(ip_address="192.168.1.1", first_time=now, latest_time=now, total_reports=0, current_reports=0).save()

        # First test: cracker without reports should not be reported
        hosts = yield controllers.get_qualifying_crackers(1, 0, now, 50, [])
        self.assertEqual(len(hosts), 0, "Cracker without reports should not be returned")

        client_ip = "1.1.1.1"
        yield controllers.add_report_to_cracker(c, client_ip, when=now)
        
        hosts = yield controllers.get_qualifying_crackers(1, -1, now-1, 50, [])
        self.assertEqual(len(hosts), 1, "When one report, get_new_hosts with resilience <0 should return one host")

        hosts = yield controllers.get_qualifying_crackers(2, -1, now-1, 50, [])
        self.assertEqual(len(hosts), 0, "When one report, get_new_hosts with resilience 0 and threshold 2 should return empty list")

        client_ip = "1.1.1.2"
        yield controllers.add_report_to_cracker(c, client_ip, when=now+3600)

        hosts = yield controllers.get_qualifying_crackers(2, 3500, now-1, 50, [])
        self.assertEqual(len(hosts), 1, "Two reports should result in a result")

        hosts = yield controllers.get_qualifying_crackers(2, 3500, now-1, 50, [c.ip_address])
        self.assertEqual(len(hosts), 0, "Two reports, remove reported host from list")

        hosts = yield controllers.get_qualifying_crackers(3, 3500, now-1, 50, [])
        self.assertEqual(len(hosts), 0, "Two reports, asked for three")

        hosts = yield controllers.get_qualifying_crackers(2, 4000, now-1, 50, [])
        self.assertEqual(len(hosts), 0, "Two reports, not enough resiliency")

        logging.debug("Testing d2")
        client_ip = "1.1.1.3"
        yield controllers.add_report_to_cracker(c, client_ip, when=now+7200)

        hosts = yield controllers.get_qualifying_crackers(2, 3500, now+3601, 50, [])
        self.assertEqual(len(hosts), 0, "Condition (d2)")

        logging.debug("Testing d1")
        client_ip = "1.1.1.3"
        yield controllers.add_report_to_cracker(c, client_ip, when=now+7200+24*3600+1)

        hosts = yield controllers.get_qualifying_crackers(2, 24*3600+1, now+3601, 50, [])
        self.assertEqual(len(hosts), 1, "Condition (d1)")

        
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
