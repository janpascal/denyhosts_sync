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

import logging
import time

from tortoise.exceptions import DoesNotExist

from . import config
from . import database
from . import models
from .models import Cracker, Report##, Legacy
from . import utils

logger = logging.getLogger(__name__)

##def get_cracker(ip_address):
##    return Cracker.find(where=["ip_address=?",ip_address], limit=1)


async def handle_report_from_client(client_ip, timestamp, hosts):
    for cracker_ip in hosts:
        if not utils.is_valid_ip_address(cracker_ip):
            logging.warning("Illegal host ip address {} from {}".format(cracker_ip, client_ip))
            raise Exception("Illegal IP address \"{}\".".format(cracker_ip))

        logging.debug("Adding report for {} from {}".format(cracker_ip, client_ip))
        await utils.wait_and_lock_host(cracker_ip)
        try:
            try:
                cracker = await Cracker.get(ip_address=cracker_ip)
            except DoesNotExist:
                cracker = Cracker(ip_address=cracker_ip, first_time=timestamp,
                    latest_time=timestamp, resiliency=0, total_reports=0, current_reports=0)
                await cracker.save()
            await add_report_to_cracker(cracker, client_ip, when=timestamp)
        finally:
            utils.unlock_host(cracker_ip)
        logging.debug("Done adding report for {} from {}".format(cracker_ip,client_ip))

# Note: lock cracker IP first!
# Report merging algorithm by Anne Bezemer, see 
# https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=622697

async def add_report_to_cracker(cracker, client_ip, when=None):
    if when is None:
        when = time.time()

    reports = await Report.filter(
        cracker_id=cracker.id, ip_address=client_ip
    ).order_by("latest_report_time")
    
    if len(reports) == 0:
        report = Report(ip_address=client_ip, first_report_time=when, latest_report_time=when)
        cracker.current_reports += 1
        report.cracker = cracker
        await report.save()
    elif len(reports) == 1:
        report = reports[0]
        # Add second report after 24 hours
        if when > report.latest_report_time + 24*3600:
            report = Report(ip_address=client_ip, first_report_time=when, latest_report_time=when)
            report.cracker = cracker
            await report.save()
    elif len(reports) == 2:
        latest_report = reports[1]
        # Add third report after again 24 hours
        if when > latest_report.latest_report_time + 24*3600:
            report = Report(ip_address=client_ip, first_report_time=when, latest_report_time=when)
            report.cracker = cracker
            await report.save()
    else:
        latest_report = reports[-1]
        latest_report.latest_report_time = when
        await latest_report.save()
    
    cracker.total_reports += 1
    cracker.latest_time = when
    cracker.resiliency = when - cracker.first_time

    await cracker.save()


async def get_qualifying_crackers(min_reports, min_resilience, previous_timestamp,
        max_crackers, latest_added_hosts):
    # Thanks to Anne Bezemer for the algorithm in this function. 
    # See https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=622697
   
    # This query takes care of conditions (a) and (b)
    # cracker_ids = await database.runGetPossibleQualifyingCrackerQuery(min_reports, min_resilience, previous_timestamp)
    ##cracker_ids = await Cracker.filter(current_reports__gte=min_reports,
    ##        resiliency__gte = min_resilience, 
    ##        latest_time__gte = previous_timestamp
    ##).order_by('-first_time').values('id', 'ip_address')# .distinct()
 
    crackers = await Cracker.filter(current_reports__gte=min_reports,
            resiliency__gte = min_resilience, 
            latest_time__gte = previous_timestamp
    ).order_by('-first_time')
    
##    database.run_query("""
##            SELECT DISTINCT c.id, c.ip_address 
##            FROM crackers c 
##            WHERE (c.current_reports >= ?)
##                AND (c.resiliency >= ?)
##                AND (c.latest_time >= ?)
##            ORDER BY c.first_time DESC
##            """, min_reports, min_resilience, previous_timestamp)
  
    if len(crackers) == 0:
        return []

    # Now look for conditions (c) and (d)
    result = []
    for cracker in crackers:
        logger.debug(f"Examing {cracker}")
        if cracker.ip_address in latest_added_hosts:
            logging.debug(f"Skipping {cracker.ip_address}, just reported by client")
            continue
        logging.debug(f"Examining cracker: {cracker}. Type: {type(cracker)}")
        reports = await cracker.reports.all().order_by("first_report_time")
        logging.debug("reports:")
        for r in reports:
            logging.debug(f"    {r}")
        logging.debug("r[m-1].first, prev: {}, {}".format(reports[min_reports-1].first_report_time, previous_timestamp))
        if (len(reports)>=min_reports and 
            reports[min_reports-1].first_report_time >= previous_timestamp): 
            # condition (c) satisfied
            logging.debug(f"Including cracker {cracker} because of (c)")
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

    logging.debug("Returning {} hosts".format(len(result)))
    return result

# Periodical database maintenance
# From algorithm by Anne Bezemer, see https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=622697
# Expiry/maintenance every hour/day:
#   remove reports with .latestreporttime older than (for example) 1 month
#     and only update cracker.currentreports
#   remove reports that were reported by what we now "reliably" know to
#     be crackers themselves
#   remove crackers that have no reports left

# TODO remove reports by identified crackers


async def perform_maintenance(limit = None):
    logging.info("Starting maintenance job...")
    
    if limit is None:
        now = time.time()
        limit = now - config.expiry_days * 24 * 3600

    reports_deleted = 0
    crackers_deleted = 0

    batch_size = 1000
  
    while True:
        old_reports = await Report.filter(latest_report_time__lt = limit).limit(batch_size)
        if len(old_reports) == 0:
            break
        logging.debug("Removing batch of {} old reports".format(len(old_reports)))
        for report in old_reports:
            await report.fetch_related('cracker')
            cracker = report.cracker
            await utils.wait_and_lock_host(cracker.ip_address)
            try:
                logging.debug("Maintenance: removing report from {} for cracker {}".format(report.ip_address, cracker.ip_address))
                ##await report.cracker.clear()
                report.cracker = None
                await report.delete()
                reports_deleted += 1

                current_reports = await cracker.reports.all().group_by('ip_address')
                cracker.current_reports = len(current_reports)
                await cracker.save()

                if cracker.current_reports == 0:
                    logging.debug("Maintenance: removing cracker {}".format(cracker.ip_address))
                    await cracker.delete()
                    crackers_deleted += 1
            finally:
                utils.unlock_host(cracker.ip_address)
            logging.debug("Maintenance on report from {} for cracker {} done".format(report.ip_address, cracker.ip_address))

    logging.info("Done maintenance job")
    logging.info("Expired {} reports and {} hosts".format(reports_deleted, crackers_deleted))
    return 0


async def purge_reported_addresses():
    await Cracker.all().delete()
    await Report.all().delete()


async def purge_ip(ip):
    # Does not work, see https://github.com/tortoise/tortoise-orm/issues/283
    # await Report.filter(cracker__ip_address = ip).delete()
    reports = await Report.filter(cracker__ip_address = ip)
    for report in reports:
        await report.delete()

    await Cracker.filter(ip_address = ip).delete()

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
