#    denyhosts sync server
#    Copyright (C) 2015-2016 Jan-Pascal van Best <janpascal@vanbest.org>

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
from twisted.python import log

import models
from models import Cracker, Report
import config
import controllers
import utils
import stats
import peering

class Server(xmlrpc.XMLRPC):
    """
    An example object to be published.
    """

    @withRequest
    @inlineCallbacks
    def xmlrpc_add_hosts(self, request, hosts):
        try:
            x_real_ip = request.received_headers.get("X-Real-IP")
            remote_ip = x_real_ip or request.getClientIP()
            now = time.time()

            logging.info("add_hosts({}) from {}".format(hosts, remote_ip))
            yield controllers.handle_report_from_client(remote_ip, now, hosts)
            try:
                yield peering.send_update(remote_ip, now, hosts)
            except xmlrpc.Fault, e:
                raise e
            except Exception, e:
                logging.warning("Error sending update to peers")
        except xmlrpc.Fault, e:
            raise e
        except Exception, e:
            log.err(_why="Exception in add_hosts")
            raise xmlrpc.Fault(104, "Error adding hosts: {}".format(e))

        returnValue(0)

    @withRequest
    @inlineCallbacks
    def xmlrpc_peering_update(self, request, key, update):
        try:
            logging.info("peering_update({}, {})".format(key, update))
            key = key.decode('hex')
            update = update.decode('base64')
            yield peering.handle_update(key, update)
        except xmlrpc.Fault, e:
            raise e
        except Exception, e:
            log.err(_why="Exception in peering_update")
            raise xmlrpc.Fault(105, "Error in peering_update({},{})".format(key, update))
        returnValue(0)

    @withRequest
    @inlineCallbacks
    def xmlrpc_peering_schema_version(self, request, key, please):
        try:
            logging.info("peering_schema_version({}, {})".format(key, please))
            key = key.decode('hex')
            please = please.decode('base64')
            result = yield peering.handle_schema_version(key, please)
            returnValue(result)
        except xmlrpc.Fault, e:
            raise e
        except Exception, e:
            log.err(_why="Exception in peering_schema_version")
            raise xmlrpc.Fault(106, "Error in peering_schema_version({},{})".format(key, please))

    @withRequest
    @inlineCallbacks
    def xmlrpc_peering_all_hosts(self, request, key, please):
        try:
            logging.info("peering_all_hosts({}, {})".format(key, please))
            key = key.decode('hex')
            please = please.decode('base64')
            result = yield peering.handle_all_hosts(key, please)
            returnValue(result)
        except xmlrpc.Fault, e:
            raise e
        except Exception, e:
            log.err(_why="Exception in peering_all_hosts")
            raise xmlrpc.Fault(106, "Error in peering_all_hosts({},{})".format(key, please))

    @withRequest
    @inlineCallbacks
    def xmlrpc_peering_all_reports_for_host(self, request, key, host):
        try:
            logging.info("peering_all_reports_for_hos({}, {})".format(key, host))
            key = key.decode('hex')
            host = host.decode('base64')
            result = yield peering.handle_all_reports_for_host(key, host)
            returnValue(result)
        except xmlrpc.Fault, e:
            raise e
        except Exception, e:
            log.err(_why="Exception in peering_all_updates_for_host")
            raise xmlrpc.Fault(107, "Error in peering_all_updates_for_host({},{})".format(key, host))

    @withRequest
    @inlineCallbacks
    def xmlrpc_peering_dump_table(self, request, key, host):
        try:
            logging.info("peering_dump_table({}, {})".format(key, host))
            key = key.decode('hex')
            host = host.decode('base64')
            result = yield peering.handle_dump_table(key, host)
            returnValue(result)
        except xmlrpc.Fault, e:
            raise e
        except Exception, e:
            log.err(_why="Exception in peering_dump_table")
            raise xmlrpc.Fault(106, "Error in peering_dump_table({},{})".format(key, host))

    @withRequest
    @inlineCallbacks
    def xmlrpc_list_peers(self, request, key, please):
        try:
            logging.info("Received list_peers call")
            logging.info("list_peers({}, {})".format(key, please))
            key = key.decode('hex')
            please = please.decode('base64')
            result = peering.list_peers(key, please)
            yield
            returnValue(result)
        except xmlrpc.Fault, e:
            raise e
        except Exception, e:
            log.err(_why="Exception in peering_list_peers")
            raise xmlrpc.Fault(108, "Error in peering_list_peers({},{})".format(key, please))
        returnValue(0)

    @withRequest
    @inlineCallbacks
    def xmlrpc_get_new_hosts(self, request, timestamp, threshold, hosts_added, resiliency):
        try:
            x_real_ip = request.received_headers.get("X-Real-IP")
            remote_ip = x_real_ip or request.getClientIP()

            logging.debug("get_new_hosts({},{},{},{}) from {}".format(timestamp, threshold, 
                hosts_added, resiliency, remote_ip))
            try:
                timestamp = long(timestamp)
                threshold = int(threshold)
                resiliency = long(resiliency)
            except:
                logging.warning("Illegal arguments to get_new_hosts from client {}".format(remote_ip))
                raise xmlrpc.Fault(102, "Illegal parameters.")

            now = time.time()
            # refuse timestamps from the future
            if timestamp > now:
                logging.warning("Illegal timestamp to get_new_hosts from client {}".format(remote_ip))
                raise xmlrpc.Fault(103, "Illegal timestamp.")

            for host in hosts_added:
                if not utils.is_valid_ip_address(host):
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
        except xmlrpc.Fault, e:
            raise e
        except Exception, e:
            log.err(_why="Exception in xmlrpc_get_new_hosts")
            raise xmlrpc.Fault(105, "Error in get_new_hosts: {}".format(str(e)))
        returnValue( result)

class WebResource(Resource):
    #isLeaf = True

    def getChild(self, name, request):
        if name == '':
            return self
        return Resource.getChild(self, name, request)

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
            request.processingFailed(err)
        stats.render_stats().addCallbacks(done, fail)
        return server.NOT_DONE_YET

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
