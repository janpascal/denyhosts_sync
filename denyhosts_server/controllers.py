# denyhosts sync server
# Copyright (C) 2015-2016 Jan-Pascal van Best <janpascal@vanbest.org>

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
from xmlrpc.client import ServerProxy

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet.threads  import deferToThread

from . import config
from . import database
from . import models
from .models import Cracker, Report, Legacy
from . import utils

def get_cracker(ip_address):
    return Cracker.find(where=["ip_address=?",ip_address], limit=1)

@inlineCallbacks
def handle_report_from_client(client_ip, timestamp, hosts, trxId=None):
    for cracker_ip in hosts:
        validIP = False
        if not utils.is_valid_ip_address(cracker_ip):
            try:
                cracker_ip_tentative = utils.getIP(cracker_ip)
                logging.debug("[TrxId:{}] Tried to convert {} in {}".format(trxId, cracker_ip, cracker_ip_tentative))
                if not utils.is_valid_ip_address(cracker_ip_tentative):
                    # Ignore the malformed ip
                    logging.warning("[TrxId:{}] Illegal host ip address {} from {} - Ignored".format(trxId, cracker_ip, client_ip))
                    raise Exception("Illegal IP address \"{}\".".format(cracker_ip))
                else:
                    validIP = True
                    logging.info("[TrxId:{}] Illegal host ip address {} converted to {} from {}".format(trxId, cracker_ip, cracker_ip_tentative, client_ip))
                    cracker_ip = cracker_ip_tentative
            except Exception:
                logging.warning("[TrxId:{}] Illegal host ip address {} from {} - Ignored due to exception".format(trxId, cracker_ip, client_ip))
                # fail gracefully!
                pass
        else:
            validIP = True

        if validIP:
            logging.debug("[TrxId:{}] Adding report for {} from {}".format(trxId, cracker_ip, client_ip))
            yield utils.wait_and_lock_host(cracker_ip)
            try:
                cracker = yield Cracker.find(where=['ip_address=?', cracker_ip], limit=1)
                if cracker is None:
                    cracker = Cracker(ip_address=cracker_ip, first_time=timestamp,
                        latest_time=timestamp, resiliency=0, total_reports=0, current_reports=0)
                    yield cracker.save()
                yield add_report_to_cracker(cracker, client_ip, when=timestamp, trxId=trxId)
            finally:
                utils.unlock_host(cracker_ip)
            logging.debug("[TrxId:{}] Done adding report for {} from {}".format(trxId, cracker_ip,client_ip))

# Note: lock cracker IP first!
# Report merging algorithm by Anne Bezemer, see 
# https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=622697
@inlineCallbacks
def add_report_to_cracker(cracker, client_ip, when=None, trxId=None):
    if when is None:
        when = int(time.time())

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
        max_crackers, latest_added_hosts, trxId=None):

    #Start measurement of elapsed time of that function to compare it with the max value (in seconds) from the config file
    aTimer = utils.Timer()
    aTimer.start()

    # Thank to Anne Bezemer for the algorithm in this function. 
    # See https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=622697
   
    # This query takes care of conditions (a) and (b)
    # cracker_ids = yield database.runGetPossibleQualifyingCrackerQuery(min_reports, min_resilience, previous_timestamp)
    # If min_reports is 1, then resiliency value must be discarded
    if min_reports == 1:
        min_resilience = 0
    cracker_ids = yield database.run_query("""
            SELECT DISTINCT c.id, c.ip_address, c.first_time, c.latest_time, c.total_reports, c.current_reports, c.resiliency 
            FROM crackers c 
            WHERE (c.current_reports >= ?)
                AND (c.resiliency >= ?)
                AND (c.latest_time >= ?)
            ORDER BY c.first_time DESC
            """, min_reports, min_resilience, previous_timestamp)
  
    if cracker_ids is None:
        returnValue([])
    logging.debug("[TrxId:{}] Retrieved {} Crackers from database".format(trxId, len(cracker_ids)))

    # Now look for conditions (c) and (d)
    result = []
    for c in cracker_ids:
        cracker_id = c[0]
        if c[1] in latest_added_hosts:
            logging.debug("[TrxId:{}] Skipping {}, just reported by client".format(trxId, c[1]))
            continue

        cracker = Cracker(id = c[0], ip_address = c[1], first_time = c[2], latest_time = c[3], total_reports = c[4], current_reports = c[5], resiliency = c[6])
        if cracker is None:
            continue
        logging.debug("[TrxId:{}] Examining ".format(trxId)+str(cracker))

        #The following statement is to be Optimized
        reports = yield cracker.reports.get(orderby="first_report_time ASC")
        logging.debug("[TrxId:{}] r[m-1].first_report_time={}, previous_timestamp={}, nb={}".format(trxId, reports[min_reports-1].first_report_time, previous_timestamp, len(reports)))
        if (len(reports)>=min_reports and 
            reports[min_reports-1].first_report_time >= previous_timestamp): 
            # condition (c) satisfied
            logging.debug("[TrxId:{}] condition (c) satisfied - Appending {}".format(trxId, cracker.ip_address))
            result.append(cracker.ip_address)
        else:
            logging.debug("[TrxId:{}] checking condition (d)...".format(trxId))
            satisfied = False
            for report in reports:
                if (not satisfied and 
                    report.latest_report_time>=previous_timestamp and
                    report.latest_report_time-cracker.first_time>=min_resilience):
                    logging.debug("[TrxId:{}]     d1".format(trxId))
                    satisfied = True
                if (report.latest_report_time<=previous_timestamp and 
                    report.latest_report_time-cracker.first_time>=min_resilience):
                    logging.debug("[TrxId:{}]     d2 failed".format(trxId))
                    satisfied = False
                    break
            if satisfied:
                logging.debug("[TrxId:{}] condition (d) satisfied - Appending {}".format(trxId, cracker.ip_address))
                result.append(cracker.ip_address)
            else:
                logging.debug("[TrxId:{}]     skipping {}".format(trxId, cracker.ip_address))
        if (aTimer.getOngoing_time()>config.max_processing_time_get_new_hosts or 
            len(result)>=max_crackers):
            break

    if len(result) < max_crackers:
        # Add results from legacy server
        extras = yield Legacy.find(where=["retrieved_time>?", previous_timestamp],
            orderby="retrieved_time DESC", limit=max_crackers-len(result))
        result = result + [extra.ip_address for extra in extras]

    logging.debug("[TrxId:{}] Returning {} hosts".format(trxId, len(result)))
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
def perform_maintenance(limit = None, legacy_limit = None):
    logging.info("Starting maintenance job...")
    
    if limit is None:
        now = int(time.time())
        limit = now - config.expiry_days * 24 * 3600

    if legacy_limit is None:
        now = int(time.time())
        legacy_limit = now - config.legacy_expiry_days * 24 * 3600

    reports_deleted = 0
    crackers_deleted = 0
    legacy_deleted = 0

    batch_size = 1000
  
    while True:
        old_reports = yield Report.find(where=["latest_report_time<?", limit], limit=batch_size)
        if len(old_reports) == 0:
            break
        logging.debug("Removing batch of {} old reports".format(len(old_reports)))
        for report in old_reports:
            cracker = yield report.cracker.get()
            yield utils.wait_and_lock_host(cracker.ip_address)
            try:
                logging.debug("Maintenance: removing report from {} for cracker {}".format(report.ip_address, cracker.ip_address))
                yield report.cracker.clear()
                yield report.delete()
                reports_deleted += 1

                current_reports = yield cracker.reports.get(group='ip_address')
                cracker.current_reports = len(current_reports)
                yield cracker.save()

                if cracker.current_reports == 0:
                    logging.debug("Maintenance: removing cracker {}".format(cracker.ip_address))
                    yield cracker.delete()
                    crackers_deleted += 1
            finally:
                utils.unlock_host(cracker.ip_address)
            logging.debug("Maintenance on report from {} for cracker {} done".format(report.ip_address, cracker.ip_address))

    legacy_reports = yield Legacy.find(where=["retrieved_time<?", legacy_limit])
    if legacy_reports is not None:
        for legacy in legacy_reports:
            yield legacy.delete()
            legacy_deleted += 1

    logging.info("Done maintenance job")
    logging.info("Expired {} reports and {} hosts, plus {} hosts from the legacy list".format(reports_deleted, crackers_deleted, legacy_deleted))
    returnValue(0)

@inlineCallbacks
def download_from_legacy_server():
    if config.legacy_server is None or config.legacy_server == "":
        returnValue(0)

    logging.info("Downloading hosts from legacy server...")
    rows = yield database.run_query('SELECT `value` FROM info WHERE `key`="last_legacy_sync"')
    last_legacy_sync_time = int(rows[0][0])

    try:
        server = yield deferToThread(ServerProxy, config.legacy_server)

        response = yield deferToThread(server.get_new_hosts, 
            last_legacy_sync_time, config.legacy_threshold, [],
            config.legacy_resiliency)
        try:
            last_legacy_sync_time = int(response["timestamp"])
        except:
            logging.ERROR("Illegal timestamp {} from legacy server".format(response["timestamp"]))
        #Registry.DBPOOL.runOperation('UPDATE info SET `value`=%s WHERE `key`="last_legacy_sync"', (str(last_legacy_sync_time),))
        database.run_operation('UPDATE info SET `value`=? WHERE `key`="last_legacy_sync"', str(last_legacy_sync_time))
        now = int(time.time())
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
    except Exception as e:
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

@inlineCallbacks
def purge_ip(ip):
    yield database.run_query("""DELETE FROM reports
        WHERE cracker_id IN (
            SELECT id FROM crackers WHERE ip_address=?
            )""", ip)
    yield database.run_query("DELETE FROM crackers WHERE ip_address=?", ip)
    yield database.run_query("DELETE FROM legacy WHERE ip_address=?", ip)
    returnValue(0)

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
