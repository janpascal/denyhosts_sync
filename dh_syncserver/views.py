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

from twisted.web import server, xmlrpc, error
from twisted.web.resource import Resource
from twisted.web.xmlrpc import withRequest
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet import reactor
import ipaddr

import models
from models import Cracker, Report
import config
import controllers
import utils
import stats

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
        logging.info("add_hosts({}) from {}".format(hosts, request.getClientIP()))
        for cracker_ip in hosts:
            if not self.is_valid_ip_address(cracker_ip):
                logging.warning("Illegal host ip address {} from {}".format(cracker_ip, request.getClientIP()))
                raise xmlrpc.Fault(101, "Illegal IP address \"{}\".".format(cracker_ip))

            logging.debug("Adding report for {} from {}".format(cracker_ip, request.getClientIP()))
            yield utils.wait_and_lock_host(cracker_ip)
            
            cracker = yield Cracker.find(where=['ip_address=?', cracker_ip], limit=1)
            if cracker is None:
                now = time.time()
                cracker = Cracker(ip_address=cracker_ip, first_time=now,
                    latest_time=now, resiliency=0, total_reports=0, current_reports=0)
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

class WebResource(Resource):
    #isLeaf = True

    #def getChild(self, name, request):
    #    logging.debug("getChild({},{})".format(name,request))
    #    if name == '':
    #        return self
    #    return Resource.getChild(self, name, request)

    def render_GET(self, request):
        logging.debug("GET({})".format(request))
        request.setHeader("Content-Type", "text/html; charset=utf-8")
        def done(result):
            if result is None:
                request.write("<h1>An error has occurred</h1>")
            else:
                request.write(result.encode('utf-8'))
            request.finish()
        def fail(err):
            #request.setResponseCode(501)
            #request.write("Server error")
            #request.write(str(err))
            #request.finish()
            request.processingFailed(err)
        stats.render_stats().addCallbacks(done, fail)
        return server.NOT_DONE_YET

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
