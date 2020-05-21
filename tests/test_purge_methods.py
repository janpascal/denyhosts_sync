# denyhosts sync server
# Copyright (C) 2015-2020 Jan-Pascal van Best <janpascal@vanbest.org>

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

async def test_purge_reports():
    now = time.time()
    c = await Cracker.create(ip_address="192.168.1.1", first_time=now, latest_time=now, total_reports=0, current_reports=0)
    c2 = await Cracker.create(ip_address="192.168.1.2", first_time=now, latest_time=now, total_reports=0, current_reports=0)
    c3 = await Cracker.create(ip_address="192.168.1.3", first_time=now, latest_time=now, total_reports=0, current_reports=0)

    await controllers.add_report_to_cracker(c, "127.0.0.1", when=now)
    await controllers.add_report_to_cracker(c, "127.0.0.2", when=now)
    await controllers.add_report_to_cracker(c, "127.0.0.9", when=now)
    await controllers.add_report_to_cracker(c2, "127.0.0.3", when=now)

    crackers = await Cracker.all()
    assert len(crackers) == 3, "Should have three crackers"

    reports = await Report.all()
    assert len(reports) == 4, "Should have four reports"
    
    await controllers.purge_reported_addresses()

    crackers = await Cracker.all()
    assert len(crackers) == 0, "Should have no crackers after purging reports"

    reports = await Report.all()
    assert len(reports) == 0, "Should have no reports after purging reports"
    

async def test_purge_ip():
    now = time.time()
    c = await Cracker.create(ip_address="192.168.211.1", first_time=now, latest_time=now, total_reports=0, current_reports=0)
    c2 = await Cracker.create(ip_address="192.168.211.2", first_time=now, latest_time=now, total_reports=0, current_reports=0)
    c3 = await Cracker.create(ip_address="192.168.211.3", first_time=now, latest_time=now, total_reports=0, current_reports=0)

    await controllers.add_report_to_cracker(c, "127.0.0.1", when=now)
    await controllers.add_report_to_cracker(c, "127.0.0.2", when=now)
    await controllers.add_report_to_cracker(c, "127.0.0.9", when=now)
    await controllers.add_report_to_cracker(c2, "127.0.0.3", when=now)

    await controllers.purge_ip("192.168.211.1")

    crackers = await Cracker.all().order_by('ip_address')
    assert len(crackers) == 2, "Should still have two crackers after purging one"
    assert crackers[0].ip_address == "192.168.211.2", "Should remove the right cracker"
    assert crackers[1].ip_address == "192.168.211.3", "Should remove the right cracker"

    reports = await Report.all()
    assert len(reports) == 1, "Should still have one report left after purging cracker with three reports"
    assert reports[0].ip_address == "127.0.0.3", "Should remove the right report"

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
