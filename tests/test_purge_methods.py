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
from dh_syncserver import database
from dh_syncserver.models import Cracker, Report, Legacy

from twisted.internet.defer import inlineCallbacks, returnValue

import base

class PurgingTest(base.TestBase):

    @inlineCallbacks
    def test_purge_reports(self):
        now = time.time()
        c = yield Cracker(ip_address="192.168.1.1", first_time=now, latest_time=now, total_reports=0, current_reports=0).save()
        c2 = yield Cracker(ip_address="192.168.1.2", first_time=now, latest_time=now, total_reports=0, current_reports=0).save()
        c3 = yield Cracker(ip_address="192.168.1.3", first_time=now, latest_time=now, total_reports=0, current_reports=0).save()

        yield controllers.add_report_to_cracker(c, "127.0.0.1", when=now)
        yield controllers.add_report_to_cracker(c, "127.0.0.2", when=now)
        yield controllers.add_report_to_cracker(c, "127.0.0.9", when=now)
        yield controllers.add_report_to_cracker(c2, "127.0.0.3", when=now)

        yield controllers.purge_legacy_addresses()

        crackers = yield Cracker.all()
        self.assertEqual(len(crackers), 3, "Should still have three crackers after purging legacy")

        reports = yield Report.all()
        self.assertEqual(len(reports), 4, "Should still have four reports after purging legacy")
        
        yield controllers.purge_reported_addresses()

        crackers = yield Cracker.all()
        self.assertEqual(len(crackers), 0, "Should have no crackers after purging reports")

        reports = yield Report.all()
        self.assertEqual(len(reports), 0, "Should have no reports after purging reports")
        
    @inlineCallbacks
    def test_purge_legacy(self):
        now = time.time()
        legacy = yield Legacy(ip_address="192.168.211.1", retrieved_time=now).save()
        legacy = yield Legacy(ip_address="192.168.211.2", retrieved_time=now).save()

        legacy = yield Legacy.all()
        self.assertEqual(len(legacy), 2, "Should have two legacy reports")

        yield controllers.purge_reported_addresses()

        legacy = yield Legacy.all()
        self.assertEqual(len(legacy), 2, "Should still have two legacy reports after purging client reports")

        yield controllers.purge_legacy_addresses()

        legacy = yield Legacy.all()
        self.assertEqual(len(legacy), 0, "Should no legacy reports after purging legacy")

        rows = yield database.run_query('SELECT `value` FROM info WHERE `key`="last_legacy_sync"')
        self.assertEqual(rows[0][0], '0', "Purging legacy should reset last legacy sync time")
        
    @inlineCallbacks
    def test_purge_ip(self):
        now = time.time()
        c = yield Cracker(ip_address="192.168.211.1", first_time=now, latest_time=now, total_reports=0, current_reports=0).save()
        c2 = yield Cracker(ip_address="192.168.211.2", first_time=now, latest_time=now, total_reports=0, current_reports=0).save()
        c3 = yield Cracker(ip_address="192.168.211.3", first_time=now, latest_time=now, total_reports=0, current_reports=0).save()

        yield controllers.add_report_to_cracker(c, "127.0.0.1", when=now)
        yield controllers.add_report_to_cracker(c, "127.0.0.2", when=now)
        yield controllers.add_report_to_cracker(c, "127.0.0.9", when=now)
        yield controllers.add_report_to_cracker(c2, "127.0.0.3", when=now)

        legacy = yield Legacy(ip_address="192.168.211.1", retrieved_time=now).save()
        legacy = yield Legacy(ip_address="192.168.211.2", retrieved_time=now).save()

        yield controllers.purge_ip("192.168.211.1")

        crackers = yield Cracker.find(orderby='ip_address ASC')
        self.assertEqual(len(crackers), 2, "Should still have two crackers after purging one")
        self.assertEquals(crackers[0].ip_address, "192.168.211.2", "Should remove the right cracker")
        self.assertEquals(crackers[1].ip_address, "192.168.211.3", "Should remove the right cracker")

        reports = yield Report.all()
        self.assertEqual(len(reports), 1, "Should still have one report left after purging cracker with three reports")
        self.assertEquals(reports[0].ip_address, "127.0.0.3", "Should remove the right report")

        legacy = yield Legacy.all()
        self.assertEqual(len(legacy), 1, "Should still have one legacy reports after purging one")
        self.assertEquals(legacy[0].ip_address, "192.168.211.2", "Should remove the right legacy host")

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
