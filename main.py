#!/usr/bin/env python

#    denyhosts sync server
#    Copyright (C) 2015 Jan-Pascal van Best <janpascal@vanbest.org>

#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.

#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sqlite3
import time

from twisted.web import server
from twisted.enterprise import adbapi
from twisted.internet import task
from twisted.internet.defer import inlineCallbacks, returnValue

from twistar.registry import Registry

import views
import models
from models import Cracker, Report
import config

# From algorithm by Anne Bezemer, see https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=622697
# Expiry/maintenance every hour/day:
#   remove reports with .latestreporttime older than (for example) 1 month
#     and only update cracker.currentreports
#   remove reports that were reported by what we now "reliably" know to
#     be crackers themselves
#   remove crackers that have no reports left

# TODO How memory intensive is this? Better by direct SQL queries?
@inlineCallbacks
def perform_maintenance():
    print("Starting maintenance job...")
    crackers = yield Cracker.all()
    if crackers is None:
        returnValue(1)

    now = time.time()
    limit = now - config.expiry_days * 24 * 3600 
    for cracker in crackers:
        reports = yield cracker.reports.get()
        for report in reports:
            if report.latest_report_time < limit:
                print("Maintenance: removing report from {} for cracker {}".format(report.ip_address, cracker.ip_address))
                cracker.current_reports -= 1
                yield report.cracker.clear()
                yield report.delete()
                yield cracker.save()
            # TODO remove reports by identified crackers
        if cracker.current_reports == 0:
            print("Maintenance: removing cracker {}".format(cracker.ip_address))
            yield cracker.delete()

    returnValue(0)
             

def create_database():
    print("Creating tables")
    db = sqlite3.connect("denyhosts.sqlite")
    db.execute("DROP TABLE IF EXISTS crackers")
    db.execute("""CREATE TABLE crackers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ip_address TEXT, 
        first_time INTEGER, 
        latest_time INTEGER, 
        total_reports INTEGER, 
        current_reports INTEGER
    )""")
    db.execute("DROP INDEX IF EXISTS cracker_ip_address")
    db.execute("CREATE INDEX cracker_ip_address ON crackers (ip_address)")
    db.execute("DROP TABLE IF EXISTS reports")
    db.execute("CREATE TABLE reports(id INTEGER PRIMARY KEY AUTOINCREMENT, cracker_id INTEGER, ip_address TEXT, first_report_time INTEGER, latest_report_time INTEGER)")
    db.execute("DROP INDEX IF EXISTS report_first_time")
    db.execute("CREATE INDEX report_first_time ON reports (first_report_time)")
    db.close()

if __name__ == '__main__':
    config.read_config("denyhosts_sync_server.conf")
    # TODO
    if config.clean_database:
        create_database()

    Registry.DBPOOL = adbapi.ConnectionPool(config.dbtype, **config.dbparams)
    Registry.register(models.Cracker, models.Report)
    from twisted.internet import reactor
    r = views.Server()
    reactor.listenTCP(8000, server.Site(r))

    # Set up maintenance job
    l = task.LoopingCall(perform_maintenance)
    l.start(config.maintenance_interval, now=False) 
    
    # Start reactor
    print("Starting reactor...")
    reactor.run()

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
