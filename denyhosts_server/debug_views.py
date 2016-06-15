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

import time
import logging
import random

from twisted.web import xmlrpc 
from twisted.web.xmlrpc import withRequest
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet import reactor
import ipaddr

import models
from models import Cracker, Report
import config
import controllers
import utils

class DebugServer(xmlrpc.XMLRPC):
    """
    Debug xmlrpc methods
    """

    def __init__(self, server):
        self.server = server

    @inlineCallbacks
    def xmlrpc_list_all_hosts(self):
        crackers = yield Cracker.all()
        returnValue([c.ip_address for c in crackers])

    # Concurrency test. Remove before public installation!
    @withRequest
    def xmlrpc_test(self, request):
        reactor.callLater(1, self.server.xmlrpc_add_hosts, request, ["1.1.1.1", "2.2.2.2"])
        reactor.callLater(1, self.server.xmlrpc_add_hosts, request, ["1.1.1.1", "2.2.2.2"])
        reactor.callLater(1, self.server.xmlrpc_add_hosts, request, ["1.1.1.1", "2.2.2.2"])
        reactor.callLater(1, self.server.xmlrpc_add_hosts, request, ["1.1.1.1", "2.2.2.2"])
        reactor.callLater(1, self.server.xmlrpc_add_hosts, request, ["1.1.1.1", "2.2.2.2"])
        reactor.callLater(1, self.server.xmlrpc_add_hosts, request, ["1.1.1.7", "2.2.2.8"])
        reactor.callLater(1, self.server.xmlrpc_add_hosts, request, ["1.1.1.7", "2.2.2.8"])
        reactor.callLater(1, self.server.xmlrpc_add_hosts, request, ["1.1.1.7", "2.2.2.8"])
        reactor.callLater(1, self.server.xmlrpc_add_hosts, request, ["1.1.1.7", "2.2.2.8"])
        reactor.callLater(1, self.server.xmlrpc_add_hosts, request, ["1.1.1.7", "2.2.2.8"])
        return 0

    # For concurrency testing. Remove before public installation!
    def xmlrpc_maintenance(self):
        return controllers.perform_maintenance()

    def random_ip_address(self):
        while True:
            ip = ".".join(map(str, (random.randint(0, 255) for _ in range(4))))
            if utils.is_valid_ip_address(ip):
                return ip
        
    _crackers = []
    @inlineCallbacks
    def xmlrpc_test_bulk_insert(self, count, same_crackers = False, when=None):
        if same_crackers and len(self._crackers) < count:
            logging.debug("Filling static crackers from {} to {}".format(len(self._crackers), count))
            for i in xrange(len(self._crackers), count):
                self._crackers.append(self.random_ip_address())

        if when is None:
            when = time.time()

        for i in xrange(count):
            reporter = self.random_ip_address()
            if same_crackers:
                cracker_ip = self._crackers[i]
            else:
                cracker_ip = self.random_ip_address()

            logging.debug("Adding report for {} from {} at {}".format(cracker_ip, reporter, when))

            yield utils.wait_and_lock_host(cracker_ip)
            
            cracker = yield Cracker.find(where=['ip_address=?', cracker_ip], limit=1)
            if cracker is None:
                cracker = Cracker(ip_address=cracker_ip, first_time=when, latest_time=when, total_reports=0, current_reports=0)
                yield cracker.save()
            yield controllers.add_report_to_cracker(cracker, reporter, when=when)
            
            utils.unlock_host(cracker_ip)
            logging.debug("Done adding report for {} from {}".format(cracker_ip,reporter))
        total = yield Cracker.count()
        total_reports = yield Report.count()
        returnValue((total,total_reports))

    def xmlrpc_clear_bulk_cracker_list(self):
        self._crackers = []
        return 0

    @inlineCallbacks
    def xmlrpc_get_cracker_info(self, ip):
        if not utils.is_valid_ip_address(ip):
            logging.warning("Illegal host ip address {}".format(ip))
            raise xmlrpc.Fault(101, "Illegal IP address \"{}\".".format(ip))
        #logging.info("Getting info for cracker {}".format(ip_address))
        cracker = yield controllers.get_cracker(ip)
        if cracker is None:
            raise xmlrpc.Fault(104, "Cracker {} unknown".format(ip))
            returnValue([])

        #logging.info("found cracker: {}".format(cracker))
        reports = yield cracker.reports.get()
        #logging.info("found reports: {}".format(reports))
        cracker_cols=['ip_address','first_time', 'latest_time', 'resiliency', 'total_reports', 'current_reports']
        report_cols=['ip_address','first_report_time', 'latest_report_time']
        returnValue( [cracker.toHash(cracker_cols), [r.toHash(report_cols) for r in reports]] )

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
