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
import logging
import os.path
import socket
import time

from twisted.internet import reactor, threads, task
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.python import log
from twistar.registry import Registry

from jinja2 import Template, Environment, FileSystemLoader

import GeoIP

import matplotlib
# Prevent errors from matplotlib instantiating a Tk windows
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

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

def insert_zeroes(rows, max = None):
    result = []
    index = 0
    if max is None:
        max = rows[-1][0] + 1

    for value in xrange(max):
        if index < len(rows) and rows[index][0] == value:
            result.append(rows[index])
            index += 1
        else:
            result.append((value,0))
    return result

def humanize_number(number, pos):
    """Return a humanized string representation of a number."""
    abbrevs = (
        (1E15, 'P'),
        (1E12, 'T'),
        (1E9, 'G'),
        (1E6, 'M'),
        (1E3, 'k'),
        (1, '')
    )
    if number < 1000:
        return str(number)
    for factor, suffix in abbrevs:
        if number >= factor:
            break
    return '%.*f%s' % (0, number / factor, suffix)

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
            if config.stats_resolve_hostnames:
                hostinfo = socket.gethostbyaddr(host.ip_address)
                host.hostname = hostinfo[0]
            else:
                host.hostname = host.ip_address
        except Exception, e:
            logging.debug("Exception looking up reverse DNS for {}: {}".format(host.ip_address, e))
            host.hostname = host.ip_address

def make_daily_graph(txn):
    # Calculate start of daily period: yesterday on the beginning of the
    # current hour
    now = time.time()
    dt_now = datetime.datetime.fromtimestamp(now)
    start_hour = dt_now.hour
    dt_onthehour = dt_now.replace(minute=0, second=0, microsecond=0)
    dt_start = dt_onthehour - datetime.timedelta(days=1)
    yesterday = int(dt_start.strftime('%s'))

    txn.execute(database.translate_query("""
        SELECT CAST((first_report_time-?)/3600 AS UNSIGNED INTEGER), count(*)
        FROM reports
        WHERE first_report_time > ?
        GROUP BY CAST((first_report_time-?)/3600 AS UNSIGNED INTEGER)
        """), (yesterday, yesterday, yesterday))
    rows = txn.fetchall()
    if not rows:
        return
    #logging.debug("Daily: {}".format(rows))
    rows = insert_zeroes(rows, 24)
    #logging.debug("Daily: {}".format(rows))

    x = [dt_start + datetime.timedelta(hours=row[0]) for row in rows]
    y = [row[1] for row in rows]

    fig = plt.figure()
    ax = fig.gca()
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=4))
    ax.set_title("Reports per hour")
    ax.plot(x,y, linestyle='solid', marker='s')
    ax.set_ybound(lower=0)
    fig.autofmt_xdate()
    fig.savefig(os.path.join(config.graph_dir, 'hourly.svg'))
    fig.clf()
    plt.close(fig)
    
def make_monthly_graph(txn):
    # Calculate start of monthly period: last month on the beginning of the
    # current day
    now = time.time()
    dt_now = datetime.datetime.fromtimestamp(now)
    start_hour = dt_now.hour
    start_day =  dt_now.day
    dt_ontheday = dt_now.replace(hour=0, minute=0, second=0, microsecond=0)
    dt_start = dt_ontheday - datetime.timedelta(weeks=4)
    yestermonth = int(dt_start.strftime('%s'))

    txn.execute(database.translate_query("""
        SELECT CAST((first_report_time-?)/24/3600 AS UNSIGNED INTEGER), count(*)
        FROM reports
        WHERE first_report_time > ?
        GROUP BY CAST((first_report_time-?)/24/3600 AS UNSIGNED INTEGER)
        """), (yestermonth, yestermonth, yestermonth))
    rows = txn.fetchall()
    if not rows:
        return

    rows = insert_zeroes(rows, 28)
    #logging.debug("Daily: {}".format(rows))

    x = [dt_start + datetime.timedelta(days=row[0]) for row in rows]
    y = [row[1] for row in rows]

    fig = plt.figure()
    ax = fig.gca()
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=4))
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(humanize_number))
    ax.set_title("Reports per day")
    ax.plot(x,y, linestyle='solid', marker='s')
    ax.set_ybound(lower=0)
    fig.autofmt_xdate()
    fig.savefig(os.path.join(config.graph_dir, 'monthly.svg'))
    fig.clf()
    plt.close(fig)

def make_contrib_graph(txn):
    # Number of reporters over days
    txn.execute(database.translate_query("""
        SELECT MIN(first_report_time) FROM reports
        """))
    first_time = txn.fetchall()
    if first_time is not None and len(first_time)>0 and first_time[0][0] is not None:
        dt_first = datetime.datetime.fromtimestamp(first_time[0][0])
    else:
        dt_first= datetime.datetime.today()
    dt_firstday = dt_first.replace(hour=0, minute=0, second=0, microsecond=0)
    firstday = int(dt_firstday.strftime("%s"))
    num_days = ( datetime.datetime.today() - dt_firstday ).days
    if num_days < 7:
        interval = 1
    elif num_days<15:
        interval = 2
    elif num_days<42:
        interval = 7
    else:
        interval = num_days / 6

    # FIXME: doesn't take into account stopped reporters
    txn.execute(database.translate_query("""
        SELECT day, COUNT(*) AS count
        FROM (
            SELECT CAST((first_report_time-?)/24/3600 AS UNSIGNED INTEGER) AS `day`, `ip_address`
            FROM reports 
            GROUP BY `day`, `ip_address`
            ) AS series 
       GROUP BY day 
       ORDER BY day ASC
        """), (firstday,))
    rows = txn.fetchall()
    if rows is None:
        return
    rows = insert_zeroes(rows, num_days)

    x = [dt_firstday + datetime.timedelta(days=row[0]) for row in rows]
    y = [row[1] for row in rows]
    fig = plt.figure()
    ax = fig.gca()
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))
    #ax.xaxis.set_major_locator(mdates.DayLocator(interval=4))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=interval))
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(humanize_number))
    ax.set_title("Number of contributors")
    ax.plot(x,y, linestyle='solid', marker='s')
    ax.set_ybound(lower=0)
    fig.autofmt_xdate()
    fig.savefig(os.path.join(config.graph_dir, 'contrib.svg'))
    fig.clf()
    plt.close(fig)

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

    logging.debug("Updating statistics cache...")
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

        logging.info("Stats: {} reports for {} hosts from {} reporters".format(
            stats["num_reports"], stats["num_hosts"], stats["num_clients"]))

        yield Registry.DBPOOL.runInteraction(make_daily_graph)
        yield Registry.DBPOOL.runInteraction(make_monthly_graph)
        yield Registry.DBPOOL.runInteraction(make_contrib_graph)
        #yield threads.deferToThread(make_daily_graph)
        #yield threads.deferToThread(make_monthly_graph)
        #yield threads.deferToThread(make_contrib_graph)

        if _cache is None:
            _cache = {}
        _cache["stats"] = stats
        _cache["time"] = time.time()
        logging.debug("Finished updating statistics cache...")
    except Exception, e:
        log.err(_why="Error updating statistics: {}".format(e))
        logging.warning("Error updating statistics: {}".format(e))

    _stats_busy = False

@inlineCallbacks
def render_stats():
    global _cache
    logging.info("Rendering statistics page...")
    if _cache is None:
        while _cache is None:
            logging.debug("No statistics cached yet, waiting for cache generation to finish...")
            yield task.deferLater(reactor, 1, lambda _:0, 0)

    now = time.time()
    try:
        env = Environment(loader=FileSystemLoader(config.template_dir))
        env.filters['datetime'] = format_datetime
        template = env.get_template('stats.html')
        html = template.render(_cache["stats"])

        logging.info("Done rendering statistics page...")
        returnValue(html)
    except Exception, e:
        log.err(_why="Error rendering statistics page: {}".format(e))
        logging.warning("Error creating statistics page: {}".format(e))

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
