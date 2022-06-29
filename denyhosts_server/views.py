#    denyhosts sync server
#    Copyright (C) 2015-2017 Jan-Pascal van Best <janpascal@vanbest.org>

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

from . import models
from .models import Cracker, Report
from . import config
from . import controllers
from . import utils
from . import stats
from . import peering

class Server(xmlrpc.XMLRPC):
    """
    An example object to be published.
    """

    @withRequest
    @inlineCallbacks
    def xmlrpc_add_hosts(self, request, hosts):
        # Identify the transaction for logging correlation
        trxId = utils.generateTrxId()

        # Timer to monitor the trx duration
        t = utils.Timer()
        t.start()

        try:
            x_real_ip = request.requestHeaders.getRawHeaders("X-Real-IP")
            remote_ip = x_real_ip[0] if x_real_ip else request.getClientIP()
            now = int(time.time())

            #Cleanup of the input as I have observed some dupe inputs creating overload on the db side
            hosts_uniq = sorted(set(hosts))
            nb_prune = len(hosts) - len(hosts_uniq)
            logging.info("[TrxId:{}] add_hosts({}) compacted by {} from {}".format(trxId, hosts_uniq, nb_prune, remote_ip))
            yield controllers.handle_report_from_client(remote_ip, now, hosts_uniq, trxId)
            try:
                yield peering.send_update(remote_ip, now, hosts_uniq)
            except xmlrpc.Fault as e:
                raise e
            except Exception as e:
                logging.warning("[TrxId:{}] Error sending update to peers".format(trxId))
        except xmlrpc.Fault as e:
            raise e
        except Exception as e:
            log.err(_why="[TrxId:{}] Exception in add_hosts".format(trxId))
            raise xmlrpc.Fault(104, "[TrxId:{}] Error adding hosts: {}".format(trxId, e))

        # Stop the Timer and log trx data
        t.stop()
        logging.info("[TrxId:{0}] add_hosts completed in {1:.3f} seconds".format(trxId, t.getElapsed_time()))
        returnValue(0)

    @withRequest
    @inlineCallbacks
    def xmlrpc_get_new_hosts(self, request, timestamp, threshold, hosts_added, resiliency):
        # Identify the transaction for logging correlation
        trxId= utils.generateTrxId()

        # Timer to monitor the trx duration
        t = utils.Timer()
        t.start()

        try:
            x_real_ip = request.requestHeaders.getRawHeaders("X-Real-IP")
            remote_ip = x_real_ip[0] if x_real_ip else request.getClientIP()

            logging.info("[TrxId:{}] get_new_hosts({},{},{},{}) from {}".format(trxId, timestamp, threshold, 
                hosts_added, resiliency, remote_ip))
            try:
                timestamp = int(timestamp)
                threshold = int(threshold)
                resiliency = int(resiliency)
            except:
                logging.warning("[TrxId:{}] Illegal arguments to get_new_hosts from client {}".format(trxId, remote_ip))
                raise xmlrpc.Fault(102, "[TrxId:{}] Illegal parameters.".format(trxId))

            now = int(time.time()) 
            # refuse timestamps from the future
            if timestamp > now:
                logging.warning("[TrxId:{}] Illegal timestamp to get_new_hosts from client {}".format(trxId, remote_ip))
                raise xmlrpc.Fault(103, "[TrxId:{}] Illegal timestamp.".format(trxId))

            for host in hosts_added:
                if not utils.is_valid_ip_address(host):
                    logging.warning("[TrxId:{}] Illegal host ip address {}".format(trxId, host))
                    raise xmlrpc.Fault(101, "[TrxId:{}] Illegal IP address \"{}\".".format(trxId, host))

            # TODO: maybe refuse timestamp from far past because it will 
            # cause much work? OTOH, denyhosts will use timestamp=0 for 
            # the first run!
            # TODO: check if client IP is a known cracker

            result = {}
            result['timestamp'] = str(int(time.time()))
            result['hosts'] = yield controllers.get_qualifying_crackers(
                    threshold, resiliency, timestamp, 
                    config.max_reported_crackers, set(hosts_added), trxId)
            logging.debug("[TrxId:{}] get_new_hosts returning: {}".format(trxId, result))
        except xmlrpc.Fault as e:
            raise e
        except Exception as e:
            log.err(_why="[TrxId:{}] Exception in xmlrpc_get_new_hosts".format(trxId))
            raise xmlrpc.Fault(105, "[TrxId:{}] Error in get_new_hosts: {}".format(trxId, str(e)))

        # Stop the Timer and log trx data
        t.stop()
        logging.info("[TrxId:{0}] get_new_hosts completed in {1:.3f} seconds returning {2} hosts".format(trxId, t.getElapsed_time(), len(result['hosts'])))
        returnValue(result)

class WebResource(Resource):
    #isLeaf = True

    def getChild(self, name, request):
        if name == b'':
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
