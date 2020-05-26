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

from denyhosts_server.models import Cracker, Report
from denyhosts_server import config
from denyhosts_server import controllers
from denyhosts_server import stats
from denyhosts_server import views



async def test_fixup():
    now = time.time()
    c1 = await Cracker.create(ip_address="194.109.6.92", first_time=now, latest_time=now, total_reports=0, current_reports=0)
    c2 = await Cracker.create(ip_address="83.163.6.54", first_time=now, latest_time=now, total_reports=0, current_reports=0)

    hosts = [c1, c2]
    config.stats_resolve_hostnames = True
    await stats.fixup_crackers(hosts)

    assert c1.hostname == "www.xs4all.nl", "Reverse DNS of www.xs4all.nl"
    assert c1.country == "Netherlands", "Testing geoip of www.xs4all.nl"

    assert c2.hostname == "vanbest.eu", "Reverse DNS of vanbest.eu"
    assert c2.country == "Netherlands", "Testing geoip of vanbest.eu"

def stats_settings():
    tests_dir = os.path.dirname(__file__)
    package_dir = os.path.dirname(tests_dir)
    config.static_dir = os.path.join(package_dir, "static")
    config.template_dir = os.path.join(package_dir, "template")
    config.graph_dir = os.path.join(os.getcwd(), "graph")
    try:
        os.mkdir(config.graph_dir)
    except OSError:
        pass
    config.stats_resolve_hostnames = False



async def prepare_stats():
    stats_settings()

    now = time.time()
    c1 = await Cracker.create(ip_address="192.168.1.1", first_time=now, latest_time=now, total_reports=0, current_reports=0)
    c2 = await Cracker.create(ip_address="192.168.1.2", first_time=now, latest_time=now, total_reports=0, current_reports=0)

    await controllers.add_report_to_cracker(c1, "127.0.0.1", when=now-25*3600)
    await controllers.add_report_to_cracker(c1, "127.0.0.2", when=now)
    await controllers.add_report_to_cracker(c1, "127.0.0.3", when=now)
    await controllers.add_report_to_cracker(c2, "127.0.0.2", when=now)
    await controllers.add_report_to_cracker(c2, "127.0.0.3", when=now+1)

    await stats.fixup_history()
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    await stats.update_country_history(yesterday, include_history=True)
    await stats.update_stats_cache()


async def test_empty_state(web_client):
    stats_settings()

    await stats.update_stats_cache()
    assert stats._cache != None, "Stats for empty database should not be None"

    cached = stats._cache["stats"]
    assert cached["num_hosts"] == 0, "Number of hosts in empty database"
    assert cached["num_reports"] == 0, "Number of reports in empty database"
    assert cached["num_clients"] == 0, "Number of clients in empty database"

    response = await web_client.get('/')
    html = await response.text()
    print(html)
    assert "Number of clients" in html, "HTML should contain number of clients"
    assert "../static/graphs/hourly.svg" in html, "HTML should contain path to hourly graph"


async def test_stats_cache():
    await prepare_stats()

    cached = stats._cache["stats"]
    #print(cached)
    assert cached["num_hosts"] == 2, "Number of hosts in database"
    assert cached["num_reports"] == 5, "Number of reports in database"
    assert cached["num_clients"] == 3, "Number of clients in database"

    assert cached["recent_hosts"][0].ip_address == "192.168.1.2", "Most recent host"
    assert len(cached["recent_hosts"]) == 2, "Reported both hosts in most recent list"

    assert cached["recent_hosts"][0].ip_address == "192.168.1.2", "Most recent host"
    assert len(cached["recent_hosts"]) == 2, "Reported both hosts in most recent list"

    assert cached["most_reported_hosts"][0].ip_address == "192.168.1.1", "Most reported host"
    assert len(cached["most_reported_hosts"]) == 2, "Reported both hosts in most reported list"

    assert os.access(os.path.join(config.graph_dir, "hourly.svg"), os.R_OK), "Creation of hourly graph"
    assert os.access(os.path.join(config.graph_dir, "monthly.svg"), os.R_OK), "Creation of monthly graph"
    assert os.access(os.path.join(config.graph_dir, "contrib.svg"), os.R_OK), "Creation of contributors graph"


async def test_stats_render(web_client):
    await prepare_stats()

    response = await web_client.get('/')
    html = await response.text()
    #print(html)
    assert "Number of clients" in html, "HTML should contain number of clients"
    assert "../static/graphs/hourly.svg" in html, "HTML should contain path to hourly graph"
    assert "127.0.0.1" not in html, "HTML should not contain reported ip addresses"
    assert html.count("192.168.1.1") == 2, "HTML should contain ip address of hosts in tables"

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
