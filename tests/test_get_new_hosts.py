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

class GetNewHostsTest(base.TestBase):

    @inlineCallbacks
    def test_get_qualifying_crackers(self):
        now = time.time()
        c = yield Cracker(ip_address="192.168.1.1", first_time=now, latest_time=now, total_reports=0, current_reports=0)
        c.save()

        # First test: cracker without reports should not be reported
        hosts = yield controllers.get_qualifying_crackers(1, 0, now, 50, [])
        self.assertEqual(len(hosts), 0, "Cracker without reports should not be returned")

        client_ip = "1.1.1.1"
        controllers.add_report_to_cracker(c, client_ip, when=now-3600)
        
        hosts = yield controllers.get_qualifying_crackers(1, -1, now-7200, 50, [])
        self.assertEqual(len(hosts), 1, "When one report, get_new_hosts with resilience 0 should return one host")

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
