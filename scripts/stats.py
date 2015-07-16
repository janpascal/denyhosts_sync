#!/usr/bin/env python

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


import argparse
import datetime
import socket
import time

from twisted.internet import task, reactor
from twisted.enterprise import adbapi
from twistar.registry import Registry
from twisted.internet.defer import inlineCallbacks, returnValue

from jinja2 import Template, Environment, PackageLoader

import GeoIP

import pygal

from dh_syncserver import config
from dh_syncserver import models
from dh_syncserver import database

def format_datetime(value, format='medium'):
    dt = datetime.datetime.fromtimestamp(value)
    if format == 'full':
        format="EEEE, d. MMMM y 'at' HH:mm:ss"
    elif format == 'medium':
        format="%a %d-%m-%Y %H:%M:%S"
    return dt.strftime(format)

def fixup_crackers(hosts):
    gi = GeoIP.new(GeoIP.GEOIP_MEMORY_CACHE)
    for host in hosts:
        try:
            host.country = gi.country_name_by_addr(host.ip_address)
        except Exception, e:
            print("Exception looking up country for {}: {}".format(host.ip_address, e))
            host.country = ''
        #host.num_reports = yield host.reports.count()
        try:
            hostinfo = socket.gethostbyaddr(host.ip_address)
            host.hostname = hostinfo[0]
        except Exception, e:
            print("Exception looking up reverse DNS for {}: {}".format(host.ip_address, e))
            host.hostname = host.ip_address
                
@inlineCallbacks
def create_stats():
    now = time.time()
    stats = {}
    stats["last_updated"] = now
    try:
        #rows = yield database.run_query("SELECT num_hosts,num_reports, num_clients, new_hosts FROM stats ORDER BY time DESC LIMIT 1")
        stats["num_hosts"] = yield models.Cracker.count()
        stats["num_reports"] = yield models.Report.count()

        rows = yield database.run_query("SELECT count(*) FROM reports GROUP BY ip_address") 
        if len(rows)>0:
            stats["num_clients"] = rows[0][0]
        else:
            stats["num_clients"] = 0

        yesterday = now - 24*3600
#        try:
#            rows_yesterday = yield database.run_query("""
#                SELECT num_hosts,num_reports, num_clients, new_hosts 
#                FROM stats 
#                WHERE time<? 
#                ORDER BY time DESC 
#                LIMIT 1""", yesterday)
#            stats["daily_reports"] = rows[0][1] - rows_yesterday[0][1] 
#        except:
#            stats["daily_reports"] = rows[0][1]
#
        stats["daily_reports"] = yield models.Report.count(where=["first_report_time>?", yesterday])
        stats["daily_new_hosts"] = yield models.Cracker.count(where=["first_time>?", yesterday])

#        try:
#            rows_totals = yield database.run_query("""
#                SELECT count(*) 
#                FROM crackers 
#                WHERE first_time>=? 
#                """, yesterday)
#            stats["daily_new_hosts"] = rows_totals[0][0]
#        except:
#            stats["daily_new_hosts"] = 0
#
        recent_hosts = yield models.Cracker.find(orderby="latest_time DESC", limit=10)
        fixup_crackers(recent_hosts)
        stats["recent_hosts"] = recent_hosts

        most_reported_hosts = yield models.Cracker.find(orderby="total_reports DESC", limit=10)
        fixup_crackers(most_reported_hosts)
        stats["most_reported_hosts"] = most_reported_hosts

        
        print("Now is {}".format(now))
        yesterday = datetime.datetime.fromtimestamp(now)
        print("Now is {}".format(yesterday))
        print("Unix timestamp is {}".format(yesterday.strftime("%s")))
        yesterday = yesterday.replace(minute=0, second=0, microsecond=0)
        start_hour = yesterday.hour
        print("Start of hour is {}".format(yesterday))
        yesterday = int(yesterday.strftime('%s'))
        print("Unix timestamp is {}".format(yesterday))
        yesterday = yesterday - 24*3600
        print("Unix timestamp yesterday is {}".format(yesterday))
        print("From yesdatday to today is {} seconds".format(now - yesterday))
        print("is {} hours".format((now - yesterday) / 3600))

        rows = yield database.run_query("""
            SELECT CAST((first_report_time-?)/3600 AS UNSIGNED INTEGER), count(*)
            FROM reports
            WHERE first_report_time > ?
            GROUP BY CAST((first_report_time-?)/3600 AS UNSIGNED INTEGER)
            """, yesterday, yesterday, yesterday)
        print(rows)
        hourly_chart = pygal.Line(show_legend = False)
        hourly_chart.title = 'Number of reports per hour (until {})'.format( datetime.datetime.fromtimestamp(now).strftime("%d-%m-%Y %H:%M:%S"))
        hourly_chart.x_labels = [ str((start_hour + row[0]) % 24) for row in rows ]
        hourly_chart.add('# of reports', [ row[1] for row in rows ])
        hourly_chart.render_to_file(filename='hourly.svg') 
        hourly_chart.render_to_png(filename='hourly.png') 

        env = Environment(loader=PackageLoader('dh_syncserver', 'templates'))
        env.filters['datetime'] = format_datetime
        template = env.get_template('stats.html')
        html = template.render(stats)

        with open('stats.html', 'w') as f:
            f.write(html)
    except Exception, e:
        print("Error creating statistics page: {}".format(e))

    reactor.stop()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="DenyHosts sync server statistics")
    parser.add_argument("-c", "--config", default="/etc/dh_syncserver.conf", help="Configuration file")
    args = parser.parse_args()

    configfile = args.config

    config.read_config(args.config)

    Registry.DBPOOL = adbapi.ConnectionPool(config.dbtype, **config.dbparams)
    Registry.register(models.Cracker, models.Report, models.Legacy)

    reactor.callLater(0, create_stats)

    reactor.run()


# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
