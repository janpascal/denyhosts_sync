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

import logging
import time
import xmlrpclib

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet.threads  import deferToThread

import config
import database
import models
from models import Cracker, Report, Legacy
import utils

def get_cracker(ip_address):
    return Cracker.find(where=["ip_address=?",ip_address], limit=1)

# Note: lock cracker IP first!
# Report merging algorithm by Anne Bezemer, see 
# https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=622697
@inlineCallbacks
def add_report_to_cracker(cracker, client_ip, when=None):
    if when is None:
        when = time.time()

    reports = yield Report.find(
        where=["cracker_id=? AND ip_address=?", cracker.id, client_ip], 
        orderby='latest_report_time ASC'
    )
    if len(reports) == 0:
        report = Report(ip_address=client_ip, first_report_time=when, latest_report_time=when)
        yield report.save()
        cracker.current_reports += 1
        yield report.cracker.set(cracker)
    elif len(reports) == 1:
        report = reports[0]
        # Add second report after 24 hours
        if when > report.latest_report_time + 24*3600:
            report = Report(ip_address=client_ip, first_report_time=when, latest_report_time=when)
            yield report.save()
            yield report.cracker.set(cracker)
    elif len(reports) == 2:
        latest_report = reports[1]
        # Add third report after again 24 hours
        if when > latest_report.latest_report_time + 24*3600:
            report = Report(ip_address=client_ip, first_report_time=when, latest_report_time=when)
            yield report.save()
            yield report.cracker.set(cracker)
    else:
        latest_report = reports[-1]
        latest_report.latest_report_time = when
        yield latest_report.save()
    
    cracker.total_reports += 1
    cracker.latest_time = when
    cracker.resiliency = when - cracker.first_time

    yield cracker.save()

@inlineCallbacks
def get_qualifying_crackers(min_reports, min_resilience, previous_timestamp,
        max_crackers, latest_added_hosts):
    # Thank to Anne Bezemer for the algorithm in this function. 
    # See https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=622697
   
    # This query takes care of conditions (a) and (b)
    # cracker_ids = yield database.runGetPossibleQualifyingCrackerQuery(min_reports, min_resilience, previous_timestamp)
    cracker_ids = yield database.run_query("""
            SELECT DISTINCT c.id, c.ip_address 
            FROM crackers c 
            WHERE (c.current_reports >= ?)
                AND (c.resiliency >= ?)
                AND (c.latest_time >= ?)
            ORDER BY c.first_time DESC
            """, min_reports, min_resilience, previous_timestamp)
  
    if cracker_ids is None:
        returnValue([])

    # Now look for conditions (c) and (d)
    result = []
    for c in cracker_ids:
        cracker_id = c[0]
        if c[1] in latest_added_hosts:
            logging.debug("Skipping {}, just reported by client".format(c[1]))
            continue
        cracker = yield Cracker.find(cracker_id)
        if cracker is None:
            continue
        logging.debug("Examining cracker:")
        logging.debug(cracker)
        reports = yield cracker.reports.get(orderby="first_report_time ASC")
        logging.debug("reports:")
#        for r in reports:
#            logging.debug("    "+str(r))
        if (len(reports)>=min_reports and 
            reports[min_reports-1].first_report_time >= previous_timestamp): 
            # condition (c) satisfied
            logging.debug("c")
            result.append(cracker.ip_address)
        else:
            logging.debug("checking (d)...")
            satisfied = False
            for report in reports:
                #logging.debug("    "+str(report))
                if (not satisfied and 
                    report.latest_report_time>=previous_timestamp and
                    report.latest_report_time-cracker.first_time>=min_resilience):
                    logging.debug("    d1")
                    satisfied = True
                if (report.latest_report_time<=previous_timestamp and 
                    report.latest_report_time-cracker.first_time>=min_resilience):
                    logging.debug("    d2 failed")
                    satisfied = False
                    break
            if satisfied:
                logging.debug("Appending {}".format(cracker.ip_address))
                result.append(cracker.ip_address)
            else:
                logging.debug("    skipping")
        if len(result)>=max_crackers:
            break

    if len(result) < max_crackers:
        # Add results from legacy server
        extras = yield Legacy.find(where=["retrieved_time>?", previous_timestamp],
            orderby="retrieved_time DESC", limit=max_crackers-len(result))
        result = result + [extra.ip_address for extra in extras]

    logging.debug("Returning {} hosts".format(len(result)))
    returnValue(result)

# Periodical database maintenance
# From algorithm by Anne Bezemer, see https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=622697
# Expiry/maintenance every hour/day:
#   remove reports with .latestreporttime older than (for example) 1 month
#     and only update cracker.currentreports
#   remove reports that were reported by what we now "reliably" know to
#     be crackers themselves
#   remove crackers that have no reports left

# TODO remove reports by identified crackers

@inlineCallbacks
def perform_maintenance(limit = None):
    logging.info("Starting maintenance job...")
    
    if limit is None:
        now = time.time()
        limit = now - config.expiry_days * 24 * 3600 

    reports_deleted = 0
    crackers_deleted = 0

    batch_size = 1000
  
    while True:
        old_reports = yield Report.find(where=["latest_report_time<?", limit], limit=batch_size)
        if len(old_reports) == 0:
            break
        logging.debug("Removing batch of {} old reports".format(len(old_reports)))
        for report in old_reports:
            cracker = yield report.cracker.get()
            yield utils.wait_and_lock_host(cracker.ip_address)
            logging.info("Maintenance: removing report from {} for cracker {}".format(report.ip_address, cracker.ip_address))
            current_reports = yield cracker.reports.get(group='ip_address')
            cracker.current_reports = len(current_reports)
            yield report.cracker.clear()
            yield report.delete()
            reports_deleted += 1
            yield cracker.save()
            if cracker.current_reports == 0:
                logging.info("Maintenance: removing cracker {}".format(cracker.ip_address))
                yield cracker.delete()
                crackers_deleted += 1
            utils.unlock_host(cracker.ip_address)
            logging.debug("Maintenance on report from {} for cracker {} done".format(report.ip_address, cracker.ip_address))

    legacy_reports = yield Legacy.find(where=["retrieved_time<?", limit])
    if legacy_reports is not None:
        for legacy in legacy_reports:
            yield legacy.delete()

    logging.info("Done maintenance job")
    logging.info("Expired {} reports and {} hosts".format(reports_deleted, crackers_deleted))
    returnValue(0)

@inlineCallbacks
def download_from_legacy_server():
    if config.legacy_server is None or config.legacy_server == "":
        returnValue(0)

    logging.info("Downloading hosts from legacy server...")
    rows = yield database.run_query('SELECT `value` FROM info WHERE `key`="last_legacy_sync"')
    last_legacy_sync_time = int(rows[0][0])

    try:
        server = yield deferToThread(xmlrpclib.ServerProxy, config.legacy_server)

        response = yield deferToThread(server.get_new_hosts, 
            last_legacy_sync_time, config.legacy_threshold, [],
            config.legacy_resiliency)
        try:
            last_legacy_sync_time = int(response["timestamp"])
        except:
            logging.ERROR("Illegal timestamp {} from legacy server".format(response["timestamp"]))
        #Registry.DBPOOL.runOperation('UPDATE info SET `value`=%s WHERE `key`="last_legacy_sync"', (str(last_legacy_sync_time),))
        database.run_operation('UPDATE info SET `value`=? WHERE `key`="last_legacy_sync"', str(last_legacy_sync_time))
        now = time.time()
        logging.debug("Got {} hosts from legacy server".format(len(response["hosts"])))
        for host in response["hosts"]:
            legacy = yield Legacy.find(where=["ip_address=?",host], limit=1)
            if legacy is None:
                logging.debug("New host from legacy server: {}".format(host))
                legacy = Legacy(ip_address=host, retrieved_time=now)
            else:
                logging.debug("Known host from legacy server: {}".format(host))
                legacy.retrieved_time = now
            yield legacy.save()
    except Exception, e:
        logging.error("Error retrieving info from legacy server: {}".format(e))

    logging.info("Done downloading hosts from legacy server.")
    returnValue(0)

@inlineCallbacks
def purge_legacy_addresses():
    yield database.run_truncate_query('legacy')
    yield database.run_query('UPDATE info SET `value`=0 WHERE `key`="last_legacy_sync"')
    returnValue(0)

@inlineCallbacks
def purge_reported_addresses():
    yield database.run_truncate_query('crackers')
    yield database.run_truncate_query('reports')
    returnValue(0)

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
