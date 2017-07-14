#!/usr/bin/env python

# denyhosts sync server
# Copyright (C) 2015-2017 Jan-Pascal van Best <janpascal@vanbest.org>

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
# Prevent errors from matplotlib instantiating a Tk window
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy

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
            host.hostname = "-"

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
        ORDER BY first_report_time ASC
        """), (yesterday, yesterday, yesterday))
    rows = txn.fetchall()
    no_data = False
    if not rows:
        logging.debug("No data for past 24 hours")
        no_data = True
        rows = [(0,0)]
    #logging.debug("Daily: {}".format(rows))
    rows = insert_zeroes(rows, 24)
    #logging.debug("Daily: {}".format(rows))

    x = [dt_start + datetime.timedelta(hours=row[0]) for row in rows]
    y = [row[1] for row in rows]

    # calc the trendline
    x_num = mdates.date2num(x)
    
    z = numpy.polyfit(x_num, y, 1)
    p = numpy.poly1d(z)
    
    xx = numpy.linspace(x_num.min(), x_num.max(), 100)
    dd = mdates.num2date(xx)
    
    fig = plt.figure()
    ax = fig.gca()
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=4))
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(humanize_number))
    ax.set_title("Reports per hour")
    ax.plot(x,y, linestyle='solid', marker='o', markerfacecolor='blue')
    ax.plot(dd, p(xx), "b--")
    ax.set_ybound(lower=0)
    fig.autofmt_xdate()
    if no_data:
        fig.text(0.5, 0.5, "Not enough data", size="x-large", 
        ha="center", va="center")
    fig.savefig(os.path.join(config.graph_dir, 'hourly.svg'))
    fig.clf()
    plt.close(fig)
    
def make_monthly_graph(txn):
    # Calculate start of monthly period: last month on the beginning of the
    # current day
    today = datetime.date.today()
    dt_start = today - datetime.timedelta(weeks=4)

    txn.execute(database.translate_query("""
        SELECT date, num_reports
        FROM history
        WHERE date >= ?
        ORDER BY date ASC
        """), (dt_start,))
    rows = txn.fetchall()
    no_data = False
    if rows is None or len(rows)==0:
        no_data = True
        x = [ today, ]
        y = [ 0, ]
    else:
        (x,y) = zip(*rows)

    # calc the trendline
    x_num = mdates.date2num(x)
   
    if not no_data:
        z = numpy.polyfit(x_num, y, 1)
        p = numpy.poly1d(z)
        xx = numpy.linspace(x_num.min(), x_num.max(), 100)
        dd = mdates.num2date(xx)
    
    fig = plt.figure()
    ax = fig.gca()
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=4))
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(humanize_number))
    ax.set_title("Reports per day")
    ax.plot(x,y, linestyle='solid', marker='o', markerfacecolor='blue')
    if not no_data:
        ax.plot(dd, p(xx),"b--")
    ax.set_ybound(lower=0)
    fig.autofmt_xdate()
    if no_data:
        fig.text(0.5, 0.5, "Not enough data", size="x-large", 
        ha="center", va="center")
    fig.savefig(os.path.join(config.graph_dir, 'monthly.svg'))
    fig.clf()
    plt.close(fig)

def make_history_graph(txn):
    # Graph since first record
    txn.execute(database.translate_query("""
        SELECT date FROM history 
        ORDER BY date ASC
        LIMIT 1
        """))
    first_time = txn.fetchall()
    if first_time is not None and len(first_time)>0 and first_time[0][0] is not None:
        dt_first = first_time[0][0]
    else:
        dt_first= datetime.date.today()
    num_days = ( datetime.date.today() - dt_first ).days
    #logging.debug("First day in data set: {}".format(dt_first))
    #logging.debug("Number of days in data set: {}".format(num_days))
    no_data = False
    if num_days == 0:
        no_data = True
        x = [ dt_first, ]
        y = [ 0, ]
    else:
        txn.execute(database.translate_query("""
            SELECT date, num_reports
            FROM history
            ORDER BY date ASC
            """))
        rows = txn.fetchall()
        (x,y) = zip(*rows)

    # calc the trendline
    x_num = mdates.date2num(x)
   
    if not no_data:
        z = numpy.polyfit(x_num, y, 1)
        p = numpy.poly1d(z)
        
        xx = numpy.linspace(x_num.min(), x_num.max(), 100)
        dd = mdates.num2date(xx)
    
    fig = plt.figure()
    ax = fig.gca()

    locator = mdates.AutoDateLocator(interval_multiples=False)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.AutoDateFormatter(locator))
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(humanize_number))
    ax.set_title("Reports per day")
    if (num_days<100):
        ax.plot(x,y, linestyle='solid', marker='o', markerfacecolor='blue')
    else:
        ax.plot(x,y, linestyle='solid', marker='')
    if not no_data:
        ax.plot(dd, p(xx),"b--")
    ax.set_ybound(lower=0)
    fig.autofmt_xdate()

    if num_days == 0:
        fig.text(0.50, 0.50, "Not enough data", size="x-large", ha="center", va="center")

    fig.savefig(os.path.join(config.graph_dir, 'history.svg'))
    fig.clf()
    plt.close(fig)

def make_contrib_graph(txn):
    # Number of reporters over days
    txn.execute(database.translate_query("""
        SELECT date FROM history 
        ORDER BY date ASC
        LIMIT 1
        """))
    first_time = txn.fetchall()
    if first_time is not None and len(first_time)>0 and first_time[0][0] is not None:
        dt_first = first_time[0][0]
    else:
        dt_first = datetime.date.today()
    num_days = ( datetime.date.today() - dt_first ).days
    if num_days == 0:
        x = [dt_first, ]
        y = [0, ]
    else:
        txn.execute(database.translate_query("""
            SELECT date, num_contributors
            FROM history
            ORDER BY date ASC
            """))
        rows = txn.fetchall()
        (x,y) = zip(*rows)

    fig = plt.figure()
    ax = fig.gca()
    locator = mdates.AutoDateLocator(interval_multiples=False)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.AutoDateFormatter(locator))
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(humanize_number))
    ax.set_title("Number of contributors")
    if (num_days<100):
        ax.plot(x,y, linestyle='solid', marker='o', markerfacecolor='blue')
    else:
        ax.plot(x,y, linestyle='solid', marker='')
    ax.set_ybound(lower=0)
    fig.autofmt_xdate()
    if num_days == 0:
        fig.text(0.50, 0.50, "Not enough data", size="x-large", ha="center", va="center")
    fig.savefig(os.path.join(config.graph_dir, 'contrib.svg'))
    fig.clf()
    plt.close(fig)

def make_country_piegraph(txn):
    # Total reports per country
    limit = 10 # Fixme configurable
    txn.execute(database.translate_query("""
        SELECT country, num_reports
        FROM country_history
        ORDER BY num_reports DESC
        LIMIT ?
        """),(limit,))

    rows = txn.fetchall()
    if rows is None or len(rows)==0:
        return

    (labels,sizes) = zip(*rows)

    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.pie(sizes, labels=labels,
            autopct='%1.1f%%', shadow=True, startangle=90)
# Set aspect ratio to be equal so that pie is drawn as a circle.
    ax.axis('equal')

    fig.savefig(os.path.join(config.graph_dir, 'country_pie.svg'))
    fig.clf()
    plt.close(fig)

def make_country_bargraph(txn):
    # Total reports per country
    limit = 10 # Fixme configurable

    txn.execute("""
        SELECT sum(num_reports)
        FROM country_history
        """)

    rows = txn.fetchall()
    no_data = False
    if rows is None or len(rows)==0 or rows[0] is None or rows[0][0] is None:
        no_data = True
        total_reports = 1
        countries = ["Unknown",]
        counts = [1,]
        max_count = 1
    else:
        total_reports = int(rows[0][0])
        
        txn.execute(database.translate_query("""
            SELECT country, num_reports
            FROM country_history
            ORDER BY num_reports DESC
            LIMIT ?
            """),(limit,))

        rows = txn.fetchall()
        if rows is None or len(rows)==0:
            return

        (countries,counts) = zip(*reversed(rows))
        max_count = max(counts)

    fig = plt.figure()
    ax = fig.add_subplot(111)

    y_pos = numpy.arange(len(countries))
    bars = ax.barh(y_pos, counts, align='center', alpha=0.6)
    count = 0
    for bar in bars:
        height = bar.get_height()
        ax.text(max_count / 20., bar.get_y() + height / 2., 
            "{}% {}".format(round(counts[count]*1.0/total_reports*100), countries[count] ),
            ha='left', va='center')
        count += 1
    ax.set_yticks(y_pos)
    ax.set_yticklabels([])
    ax.set_title('Number of attacks per country of origin (top {})'.format(limit))
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(humanize_number))
    ax.set_ylim(ymin=-1)
    fig.tight_layout()
    if no_data:
        fig.text(0.50, 0.50, "Not enough data", size="x-large", ha="center", va="center")

    fig.savefig(os.path.join(config.graph_dir, 'country_bar.svg'))
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

    # Fill history table for yesterday, when necessary
    yield update_recent_history()
    yield update_country_history()

    now = time.time()
    stats = {}
    stats["last_updated"] = now
    stats["has_hostnames"] = config.stats_resolve_hostnames
    # Note paths configured in main.py by the Resource objects
    stats["static_base"] = "../static"
    stats["graph_base"] = "../static/graph"
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
        yield Registry.DBPOOL.runInteraction(make_history_graph)
        yield Registry.DBPOOL.runInteraction(make_country_bargraph)

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

def update_history_txn(txn, date):
    try:
        logging.info("Updating history table for {}".format(date))
        start = time.mktime(date.timetuple())
        end = start + 24*60*60
        #logging.debug("Date start, end: {}, {}".format(start, end))

        txn.execute(database.translate_query("""
                SELECT  COUNT(*), 
                        COUNT(DISTINCT cracker_id),
                        COUNT(DISTINCT ip_address) 
                FROM reports 
                WHERE (first_report_time>=? AND first_report_time<?) OR
                      (latest_report_time>=? AND latest_report_time<?)
                """), (start, end, start, end))
        rows = txn.fetchall()
        if rows is None or len(rows)==0:
            return

        num_reports = rows[0][0]
        num_hosts = rows[0][1]
        num_reporters = rows[0][2]
        logging.debug("Number of reporters: {}".format(num_reporters))
        logging.debug("Number of reports: {}".format(num_reports))
        logging.debug("Number of reported hosts: {}".format(num_hosts))

        txn.execute(database.translate_query("""
            REPLACE INTO history
                (date, num_reports, num_contributors, num_reported_hosts)
                VALUES (?,?,?,?)
            """), (date, num_reports, num_reporters, num_hosts))
    except Exception, e:
        log.err(_why="Error updating history: {}".format(e))
        logging.warning("Error updating history: {}".format(e))

def update_recent_history_txn(txn, last_date=None):
    "date should be a datetime.date or None, indicating yesterday"
    if last_date is None:
        last_date = datetime.date.today() - datetime.timedelta(days = 1)

    try:
        # First find last date for which the history has already been filled
        txn.execute("""SELECT max(date) AS "MAXDATE [DATE]" FROM history""") 
        rows = txn.fetchall()
        if rows is not None and len(rows)>0 and rows[0][0] is not None:
            last_filled_date = rows[0][0]
        else:
            txn.execute("SELECT MIN(first_report_time) FROM reports")
            first_time = txn.fetchall()
            if first_time is not None and len(first_time)>0 and first_time[0][0] is not None:
                last_filled_date = datetime.date.fromtimestamp(first_time[0][0])
            else:
                last_filled_date = datetime.date.today()

        first_date = last_filled_date + datetime.timedelta(days=1)
        # Then fill history
        date = first_date
        while date <= last_date:
            update_history_txn(txn, date)
            date = date + datetime.timedelta(days = 1)

    except Exception as e:
        log.err(_why="Error updating history: {}".format(e))
        logging.warning("Error updating history: {}".format(e))

    
def fixup_history_txn(txn):
    try:
        txn.execute("SELECT MIN(first_report_time) FROM reports")
        first_time = txn.fetchall()
        if first_time is not None and len(first_time)>0 and first_time[0][0] is not None:
            first_date = datetime.date.fromtimestamp(first_time[0][0])
        else:
            # No data, nothing to do
            return

        last_date = datetime.date.today() - datetime.timedelta(days = 1)

        # Find any dates for which the history has not been filled
        txn.execute("SELECT date FROM history ORDER BY date ASC") 
        rows = txn.fetchall()
        dates = set([row[0] for row in rows])

        date = first_date
        while date <= last_date:
            if date not in dates:
                update_history_txn(txn, date)
            date = date + datetime.timedelta(days = 1)

    except Exception as e:
        log.err(_why="Error fixing up history: {}".format(e))
        logging.warning("Error fixing up history: {}".format(e))

def update_recent_history(date=None):
    "date should be a datetime.date or None, indicating yesterday"
    return Registry.DBPOOL.runInteraction(update_recent_history_txn, date)

def update_country_history_txn(txn, date=None, include_history = False):
    if date is None:
        date = datetime.date.today() - datetime.timedelta(days = 1)

    if include_history:
        start_time = 0
    else:
        start_time = (date - datetime.date(1970, 1, 1)).total_seconds()
    end_time = (date + datetime.timedelta(days=1) - datetime.date(1970, 1, 1)).total_seconds()

    txn.execute("SELECT country_code,country,num_reports FROM country_history")
    rows = txn.fetchall()
    result = {row[0]:(row[1],row[2]) for row in rows}

    gi = GeoIP.new(GeoIP.GEOIP_MEMORY_CACHE)

    txn.execute(database.translate_query(
        """SELECT crackers.ip_address,COUNT(*) as count
        FROM crackers LEFT JOIN reports ON reports.cracker_id = crackers.id
        WHERE reports.first_report_time >= ? AND reports.first_report_time < ?
        GROUP BY crackers.id
        """), (start_time, end_time))

    while True:
        rows = txn.fetchmany(size=100)
        if len(rows) == 0:
            break
        for row in rows:
            ip = row[0]
            count = row[1]
            try:
                country_code = gi.country_code_by_addr(ip)
                country = gi.country_name_by_addr(ip)
                if country_code is None:
                    country_code = "ZZ"
                if country is None:
                    country = "(Unknown)"
                if country_code in result:
                    count += result[country_code][1]
                result[country_code] = (country,count)
            except Exception, e:
                logging.debug("Exception looking up country for {}: {}".format(ip, e))
     
    for country_code in result:
        country,count = result[country_code]
        txn.execute(database.translate_query(
            """REPLACE INTO country_history (country_code,country,num_reports)
            VALUES (?,?,?)"""),
            (country_code,country,count))

def update_country_history(date=None, include_history=False):
    "date should be a datetime.date or None, indicating yesterday"
    return Registry.DBPOOL.runInteraction(update_country_history_txn, date, include_history)

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
