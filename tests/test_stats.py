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

import datetime
import inspect
import os
import os.path
import time
import traceback

from dh_syncserver.models import Cracker, Report, Legacy
from dh_syncserver import config
from dh_syncserver import controllers
from dh_syncserver import stats

from twisted.internet.defer import inlineCallbacks, returnValue

from twistar.registry import Registry

import base

class StatsTest(base.TestBase):

    @inlineCallbacks
    def test_fixup(self):
        now = time.time()
        c1 = yield Cracker(ip_address="194.109.6.92", first_time=now, latest_time=now, total_reports=0, current_reports=0).save()
        c2 = yield Cracker(ip_address="192.30.252.128", first_time=now, latest_time=now, total_reports=0, current_reports=0).save()

        hosts = [c1, c2]
        config.stats_resolve_hostnames = True
        stats.fixup_crackers(hosts)

        self.assertEqual(c1.hostname, "www.xs4all.nl", "Reverse DNS of www.xs4all.nl")
        self.assertEqual(c1.country, "Netherlands", "Testing geoip of www.xs4all.nl")

        self.assertEqual(c2.hostname, "github.com", "Reverse DNS of github.com")
        self.assertEqual(c2.country, "United States", "Testing geoip of github.com")

    def stats_settings(self):
        tests_dir = os.path.dirname(inspect.getsourcefile(self.__class__))
        package_dir = os.path.dirname(tests_dir)
        config.static_dir = os.path.join(package_dir, "static")
        config.template_dir = os.path.join(package_dir, "template")
        config.graph_dir = os.path.join(os.getcwd(), "graph")
        try:
            os.mkdir(config.graph_dir)
        except OSError:
            pass
        config.stats_resolve_hostnames = False


    @inlineCallbacks
    def prepare_stats(self):
        self.stats_settings()

        now = time.time()
        c1 = yield Cracker(ip_address="192.168.1.1", first_time=now, latest_time=now, total_reports=0, current_reports=0).save()
        c2 = yield Cracker(ip_address="192.168.1.2", first_time=now, latest_time=now, total_reports=0, current_reports=0).save()

        yield controllers.add_report_to_cracker(c1, "127.0.0.1", when=now-25*3600)
        yield controllers.add_report_to_cracker(c1, "127.0.0.2", when=now)
        yield controllers.add_report_to_cracker(c1, "127.0.0.3", when=now)
        yield controllers.add_report_to_cracker(c2, "127.0.0.2", when=now)
        yield controllers.add_report_to_cracker(c2, "127.0.0.3", when=now+1)

        yield Registry.DBPOOL.runInteraction(stats.fixup_history_txn)
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        yield Registry.DBPOOL.runInteraction(stats.update_country_history_txn, yesterday, include_history=True)
        yield stats.update_stats_cache()

    @inlineCallbacks
    def test_empty_state(self):
        self.stats_settings()

        yield stats.update_stats_cache()
        self.assertIsNotNone(stats._cache, "Stats for empty database should not be None")

        cached = stats._cache["stats"]
        self.assertEqual(cached["num_hosts"], 0, "Number of hosts in empty database")
        self.assertEqual(cached["num_reports"], 0, "Number of reports in empty database")
        self.assertEqual(cached["num_clients"], 0, "Number of clients in empty database")

        html = yield stats.render_stats()
        #print(html)
        self.assertTrue("Number of clients" in html, "HTML should contain number of clients")
        self.assertTrue("../static/graphs/hourly.svg" in html, "HTML should contain path to hourly graph")

    @inlineCallbacks
    def test_stats_cache(self):
        yield self.prepare_stats()

        cached = stats._cache["stats"]
        print(cached)
        self.assertEqual(cached["num_hosts"], 2, "Number of hosts in database")
        self.assertEqual(cached["num_reports"], 5, "Number of reports in database")
        self.assertEqual(cached["num_clients"], 3, "Number of clients in database")

        self.assertEquals(cached["recent_hosts"][0].ip_address, "192.168.1.2", "Most recent host")
        self.assertEquals(len(cached["recent_hosts"]), 2, "Reported both hosts in most recent list")

        self.assertEquals(cached["recent_hosts"][0].ip_address, "192.168.1.2", "Most recent host")
        self.assertEquals(len(cached["recent_hosts"]), 2, "Reported both hosts in most recent list")

        self.assertEquals(cached["most_reported_hosts"][0].ip_address, "192.168.1.1", "Most reported host") 
        self.assertEquals(len(cached["most_reported_hosts"]), 2, "Reported both hosts in most reported list")

        self.assertTrue(os.access(os.path.join(config.graph_dir, "hourly.svg"), os.R_OK), "Creation of hourly graph")
        self.assertTrue(os.access(os.path.join(config.graph_dir, "monthly.svg"), os.R_OK), "Creation of monthly graph")
        self.assertTrue(os.access(os.path.join(config.graph_dir, "contrib.svg"), os.R_OK), "Creation of contributors graph")

    @inlineCallbacks
    def test_stats_render(self):
        yield self.prepare_stats()

        html = yield stats.render_stats()
        #print(html)
        self.assertTrue("Number of clients" in html, "HTML should contain number of clients")
        self.assertTrue("../static/graphs/hourly.svg" in html, "HTML should contain path to hourly graph")
        self.assertFalse("127.0.0.1" in html, "HTML should not contain reported ip addresses")
        self.assertEqual(html.count("192.168.1.1"), 2, "HTML should contain ip address of hosts in tables")

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
