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

class Server(xmlrpc.XMLRPC):
    """
    An example object to be published.
    """

    @staticmethod
    def is_valid_ip_address(ip_address):
        try:
            ip = ipaddr.IPAddress(ip_address)
        except:
            return False
        if (ip.is_reserved or ip.is_private or ip.is_loopback or
            ip.is_unspecified or ip.is_multicast or
            ip.is_link_local):
            return False
        return True

    @withRequest
    @inlineCallbacks
    def xmlrpc_add_hosts(self, request, hosts):
        logging.debug("add_hosts({}) from {}".format(hosts, request.getClientIP()))
        for cracker_ip in hosts:
            if not self.is_valid_ip_address(cracker_ip):
                logging.warning("Illegal host ip address {} from {}".format(cracker_ip, request.getClientIP()))
                raise xmlrpc.Fault(101, "Illegal IP address \"{}\".".format(cracker_ip))

            logging.debug("Adding report for {} from {}".format(cracker_ip, request.getClientIP()))
            yield utils.wait_and_lock_host(cracker_ip)
            
            cracker = yield Cracker.find(where=['ip_address=?', cracker_ip], limit=1)
            if cracker is None:
                now = time.time()
                cracker = Cracker(ip_address=cracker_ip, first_time=now, latest_time=now, total_reports=0, current_reports=0)
                yield cracker.save()
            yield controllers.add_report_to_cracker(cracker, request.getClientIP())
            
            utils.unlock_host(cracker_ip)
            logging.debug("Done adding report for {} from {}".format(cracker_ip,request.getClientIP()))

        returnValue(0)

    @withRequest
    @inlineCallbacks
    def xmlrpc_get_new_hosts(self, request, timestamp, threshold, hosts_added, resiliency):
        logging.debug("get_new_hosts({},{},{},{}) from {}".format(timestamp, threshold, 
            hosts_added, resiliency, request.getClientIP()))
        try:
            timestamp = long(timestamp)
            threshold = int(threshold)
            resiliency = long(resiliency)
        except:
            logging.warning("Illegal arguments to get_new_hosts from client {}".format(request.getClientIP()))
            raise xmlrpc.Fault(102, "Illegal parameters.")

        now = time.time()
        # refuse timestamps from the future
        if timestamp > now:
            logging.warning("Illegal timestamp to get_new_hosts from client {}".format(request.getClientIP()))
            raise xmlrpc.Fault(103, "Illegal timestamp.")

        for host in hosts_added:
            if not self.is_valid_ip_address(host):
                logging.warning("Illegal host ip address {}".format(host))
                raise xmlrpc.Fault(101, "Illegal IP address \"{}\".".format(host))


        # TODO: maybe refuse timestamp from far past because it will 
        # cause much work? OTOH, denyhosts will use timestamp=0 for 
        # the first run!
        # TODO: check if client IP is a known cracker

        result = {}
        result['timestamp'] = str(long(time.time()))
        result['hosts'] = yield controllers.get_qualifying_crackers(
                threshold, resiliency, timestamp, 
                config.max_reported_crackers, set(hosts_added))
        logging.debug("returning: {}".format(result))
        returnValue( result)

    @inlineCallbacks
    def xmlrpc_list_all_hosts(self):
        crackers = yield Cracker.all()
        returnValue([c.ip_address for c in crackers])

    # Concurrency test. Remove before public installation!
    @withRequest
    def xmlrpc_test(self, request):
        reactor.callLater(1, self.xmlrpc_add_hosts, request, ["1.1.1.1", "2.2.2.2"])
        reactor.callLater(1, self.xmlrpc_add_hosts, request, ["1.1.1.1", "2.2.2.2"])
        reactor.callLater(1, self.xmlrpc_add_hosts, request, ["1.1.1.1", "2.2.2.2"])
        reactor.callLater(1, self.xmlrpc_add_hosts, request, ["1.1.1.1", "2.2.2.2"])
        reactor.callLater(1, self.xmlrpc_add_hosts, request, ["1.1.1.1", "2.2.2.2"])
        reactor.callLater(1, self.xmlrpc_add_hosts, request, ["1.1.1.7", "2.2.2.8"])
        reactor.callLater(1, self.xmlrpc_add_hosts, request, ["1.1.1.7", "2.2.2.8"])
        reactor.callLater(1, self.xmlrpc_add_hosts, request, ["1.1.1.7", "2.2.2.8"])
        reactor.callLater(1, self.xmlrpc_add_hosts, request, ["1.1.1.7", "2.2.2.8"])
        reactor.callLater(1, self.xmlrpc_add_hosts, request, ["1.1.1.7", "2.2.2.8"])
        return 0

    # For concurrency testing. Remove before public installation!
    def xmlrpc_maintenance(self):
        return controllers.perform_maintenance()

    def random_ip_address(self):
        while True:
            ip = ".".join(map(str, (random.randint(0, 255) for _ in range(4))))
            if self.is_valid_ip_address(ip):
                return ip
        
    _crackers = []
    @inlineCallbacks
    def xmlrpc_test_bulk_insert(self, count, same_crackers = False):
        if same_crackers and len(self._crackers) < count:
            logging.debug("Filling static crackers from {} to {}".format(len(self._crackers), count))
            for i in xrange(len(self._crackers), count):
                self._crackers.append(self.random_ip_address())

        for i in xrange(count):
            reporter = self.random_ip_address()
            if same_crackers:
                cracker_ip = self._crackers[i]
            else:
                cracker_ip = self.random_ip_address()

            logging.debug("Adding report for {} from {}".format(cracker_ip, reporter))

            yield utils.wait_and_lock_host(cracker_ip)
            
            cracker = yield Cracker.find(where=['ip_address=?', cracker_ip], limit=1)
            if cracker is None:
                now = time.time()
                cracker = Cracker(ip_address=cracker_ip, first_time=now, latest_time=now, total_reports=0, current_reports=0)
                yield cracker.save()
            yield controllers.add_report_to_cracker(cracker, reporter)
            
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
        if not self.is_valid_ip_address(ip):
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
        cracker_cols=['ip_address','first_time', 'latest_time', 'total_reports', 'current_reports']
        report_cols=['ip_address','first_report_time', 'latest_report_time']
        returnValue( [cracker.toHash(cracker_cols), [r.toHash(report_cols) for r in reports]] )

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
