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

from twisted.internet.defer import inlineCallbacks, returnValue

import config
import models
from models import Cracker, Report

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
    logging.info("Starting maintenance job...")
    crackers = yield Cracker.all()
    if crackers is None:
        returnValue(1)

    now = time.time()
    limit = now - config.expiry_days * 24 * 3600 
    for cracker in crackers:
        reports = yield cracker.reports.get()
        for report in reports:
            if report.latest_report_time < limit:
                logging.info("Maintenance: removing report from {} for cracker {}".format(report.ip_address, cracker.ip_address))
                cracker.current_reports -= 1
                yield report.cracker.clear()
                yield report.delete()
                yield cracker.save()
            # TODO remove reports by identified crackers
        if cracker.current_reports == 0:
            logging.info("Maintenance: removing cracker {}".format(cracker.ip_address))
            yield cracker.delete()

    returnValue(0)

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
