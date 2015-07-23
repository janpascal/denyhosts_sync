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


import config
import datetime
import socket
import os.path
import time
import logging

from twisted.internet import reactor, threads
from twisted.internet.defer import inlineCallbacks, returnValue

from jinja2 import Template, Environment, FileSystemLoader

import GeoIP

import pygal
from pygal.style import CleanStyle

import models
import database
import __init__

def format_datetime(value, format='medium'):
    dt = datetime.datetime.fromtimestamp(value)
    if format == 'full':
        format="EEEE, d. MMMM y 'at' HH:mm:ss"
    elif format == 'medium':
        format="%a %d-%m-%Y %H:%M:%S"
    return dt.strftime(format)

# Functions containing blocking io, call from thread!
def fixup_crackers(hosts):
    gi = GeoIP.new(GeoIP.GEOIP_MEMORY_CACHE)
    for host in hosts:
        try:
            host.country = gi.country_name_by_addr(host.ip_address)
        except Exception, e:
            logging.debug("Exception looking up country for {}: {}".format(host.ip_address, e))
            host.country = ''
        try:
            hostinfo = socket.gethostbyaddr(host.ip_address)
            host.hostname = hostinfo[0]
            #host.hostname = 'disabled'
        except Exception, e:
            logging.debug("Exception looking up reverse DNS for {}: {}".format(host.ip_address, e))
            host.hostname = host.ip_address

_cache = None
_stats_busy = False

@inlineCallbacks
def update_stats_cache():
    global _stats_busy
    global _cache
    if _stats_busy:
        logging.debug("Already updating statistics cache, exiting")
        returnValue(None)
    _stats_busy = True

    logging.info("Updating statistics cache...")
    now = time.time()
    stats = {}
    stats["last_updated"] = now
    # Note paths configured in main.py by the Resource objects
    stats["static_base"] = "../static"
    stats["graph_base"] = "../static/graphs"
    stats["server_version"] = __init__.version
    try:
        #rows = yield database.run_query("SELECT num_hosts,num_reports, num_clients, new_hosts FROM stats ORDER BY time DESC LIMIT 1")
        stats["num_hosts"] = yield models.Cracker.count()
        stats["num_reports"] = yield models.Report.count()

        rows = yield database.run_query("SELECT count(DISTINCT ip_address) FROM reports") 
        if len(rows)>0:
            stats["num_clients"] = rows[0][0]
        else:
            stats["num_clients"] = 0

        yesterday = now - 24*3600
        stats["daily_reports"] = yield models.Report.count(where=["first_report_time>?", yesterday])
        stats["daily_new_hosts"] = yield models.Cracker.count(where=["first_time>?", yesterday])

        recent_hosts = yield models.Cracker.find(orderby="latest_time DESC", limit=10)
        yield threads.deferToThread(fixup_crackers, recent_hosts)
        stats["recent_hosts"] = recent_hosts

        most_reported_hosts = yield models.Cracker.find(orderby="total_reports DESC", limit=10)
        yield threads.deferToThread(fixup_crackers, most_reported_hosts)
        stats["most_reported_hosts"] = most_reported_hosts

        # Calculate start of daily period: yesterday on the beginning of the
        # current hour
        dt_now = datetime.datetime.fromtimestamp(now)
        start_hour = dt_now.hour
        dt_onthehour = dt_now.replace(minute=0, second=0, microsecond=0)
        dt_start = dt_onthehour - datetime.timedelta(days=1)
        yesterday = int(dt_start.strftime('%s'))

        # FIXME: because of the SQL queries used, hours without any reports will 
        # be omitted from the resulting graph
        rows = yield database.run_query("""
            SELECT CAST((first_report_time-?)/3600 AS UNSIGNED INTEGER), count(*)
            FROM reports
            WHERE first_report_time > ?
            GROUP BY CAST((first_report_time-?)/3600 AS UNSIGNED INTEGER)
            """, yesterday, yesterday, yesterday)
        hourly_chart = pygal.Line(show_legend = False, style=CleanStyle, human_readable = True)
        hourly_chart.title = 'Number of reports per hour (until {})'.format( datetime.datetime.fromtimestamp(now).strftime("%d-%m-%Y %H:%M:%S"))
        hourly_chart.x_labels = [ str((start_hour + row[0]) % 24) for row in rows ]
        hourly_chart.add('# of reports', [ row[1] for row in rows ])
        hourly_chart.render_to_file(filename=os.path.join(config.graph_dir, 'hourly.svg'))

        # Calculate start of monthly period: last month on the beginning of the
        # current day
        dt_now = datetime.datetime.fromtimestamp(now)
        start_hour = dt_now.hour
        start_day =  dt_now.day
        dt_ontheday = dt_now.replace(hour=0, minute=0, second=0, microsecond=0)
        dt_start = dt_onthehour - datetime.timedelta(weeks=4)
        yestermonth = int(dt_start.strftime('%s'))

        # FIXME: also days without reports will be omitted
        rows = yield database.run_query("""
            SELECT CAST((first_report_time-?)/24/3600 AS UNSIGNED INTEGER), count(*)
            FROM reports
            WHERE first_report_time > ?
            GROUP BY CAST((first_report_time-?)/24/3600 AS UNSIGNED INTEGER)
            """, yestermonth, yestermonth, yestermonth)
        daily_chart = pygal.Line(show_legend = False, style=CleanStyle, human_readable = True)
        daily_chart.title = 'Number of reports per day (until {})'.format( datetime.datetime.fromtimestamp(now).strftime("%d-%m-%Y %H:%M:%S"))
        daily_chart.x_labels = [ str((dt_start + datetime.timedelta(days=row[0])).day) for row in rows ]
        daily_chart.add('# of reports', [ row[1] for row in rows ])
        daily_chart.render_to_file(filename=os.path.join(config.graph_dir, 'monthly.svg'))

        # Number of reporters over days
        logging.debug("Creating graph for contributors")
        first_time  = yield database.run_query("""
            SELECT MIN(first_report_time) FROM reports
            """)
        dt_first = datetime.datetime.fromtimestamp(first_time[0][0])
        dt_firstday = dt_first.replace(hour=0, minute=0, second=0, microsecond=0)
        firstday = int(dt_firstday.strftime("%s"))
        logging.debug("first day: {}".format(dt_firstday))
        rows = yield database.run_query(""" 
            SELECT CAST((start_time-?)/24/3600 AS UNSIGNED INTEGER) AS day, COUNT(*) AS count
            FROM (
                SELECT MIN(first_report_time) AS start_time 
                FROM reports 
                GROUP BY ip_address
                ) AS series 
           GROUP BY day 
           ORDER BY day ASC
            """, firstday)
        accumulated_reporters = reduce(lambda l,x: l + ((x[0],l[-1][1]+x[1]),), rows[1:], rows[:1])
        #logging.debug("Reporters: {}".format(accumulated_reporters))
        reporters_chart = pygal.DateLine(show_legend = False, style=CleanStyle,
            human_readable = True,
            x_label_rotation=20)
        reporters_chart.title = 'Number of contributors'
        reporters_chart.x_label_format = "%Y-%m-%d"
        #reporters_chart.x_labels = [ str((dt_firstday+ datetime.timedelta(days=row[0])).day) for row in accumulated_reporters]
        reporters_chart.add('# of contributors', [ 
            (dt_firstday + datetime.timedelta(days=row[0]), row[1]) for row in accumulated_reporters])
        reporters_chart.render_to_file(filename=os.path.join(config.graph_dir, 'contrib.svg'))

        if _cache is None:
            _cache = {}
        _cache["stats"] = stats
        _cache["time"] = time.time()
    except Exception, e:
        logging.warning("Error updating statistics: {}".format(e))

    _stats_busy = False

@inlineCallbacks
def render_stats():
    global _cache
    logging.info("Rendering statistics page...")
    if _cache is None:
        logging.debug("No statistics cached yet, doing that now...")
        yield update_stats_cache()

    now = time.time()
    try:
        env = Environment(loader=FileSystemLoader(config.template_dir))
        env.filters['datetime'] = format_datetime
        template = env.get_template('stats.html')
        html = template.render(_cache["stats"])

        logging.info("Done rendering statistics page...")
        returnValue(html)
    except Exception, e:
        logging.warning("Error creating statistics page: {}".format(e))

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
