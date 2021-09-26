
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

from . import models
from .models import Cracker, Report
from . import config
from . import controllers
from . import utils
from . import stats
from . import peering

class PeeringServer(xmlrpc.XMLRPC):
    """
    Peering xmlrpc methods
    """

    @withRequest
    @inlineCallbacks
    def xmlrpc_update(self, request, key, update):
        try:
            logging.info("update({}, {})".format(key, update))
            key = key.decode('hex')
            update = update.decode('base64')
            yield peering.handle_update(key, update)
        except xmlrpc.Fault as e:
            raise e
        except Exception as e:
            log.err(_why="Exception in update")
            raise xmlrpc.Fault(105, "Error in update({},{})".format(key, update))
        returnValue(0)

    @withRequest
    @inlineCallbacks
    def xmlrpc_schema_version(self, request, key, please):
        try:
            logging.info("schema_version({}, {})".format(key, please))
            key = key.decode('hex')
            please = please.decode('base64')
            result = yield peering.handle_schema_version(key, please)
            returnValue(result)
        except xmlrpc.Fault as e:
            raise e
        except Exception as e:
            log.err(_why="Exception in schema_version")
            raise xmlrpc.Fault(106, "Error in schema_version({},{})".format(key, please))

    @withRequest
    @inlineCallbacks
    def xmlrpc_all_hosts(self, request, key, please):
        try:
            logging.info("all_hosts({}, {})".format(key, please))
            key = key.decode('hex')
            please = please.decode('base64')
            result = yield peering.handle_all_hosts(key, please)
            returnValue(result)
        except xmlrpc.Fault as e:
            raise e
        except Exception as e:
            log.err(_why="Exception in all_hosts")
            raise xmlrpc.Fault(106, "Error in all_hosts({},{})".format(key, please))

    @withRequest
    @inlineCallbacks
    def xmlrpc_all_reports_for_host(self, request, key, host):
        try:
            logging.info("all_reports_for_hos({}, {})".format(key, host))
            key = key.decode('hex')
            host = host.decode('base64')
            result = yield peering.handle_all_reports_for_host(key, host)
            returnValue(result)
        except xmlrpc.Fault as e:
            raise e
        except Exception as e:
            log.err(_why="Exception in all_updates_for_host")
            raise xmlrpc.Fault(107, "Error in all_updates_for_host({},{})".format(key, host))

    @withRequest
    @inlineCallbacks
    def xmlrpc_dump_table(self, request, key, host):
        try:
            logging.info("dump_table({}, {})".format(key, host))
            key = key.decode('hex')
            host = host.decode('base64')
            result = yield peering.handle_dump_table(key, host)
            returnValue(result)
        except xmlrpc.Fault as e:
            raise e
        except Exception as e:
            log.err(_why="Exception in dump_table")
            raise xmlrpc.Fault(106, "Error in dump_table({},{})".format(key, host))

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
        except xmlrpc.Fault as e:
            raise e
        except Exception as e:
            log.err(_why="Exception in list_peers")
            raise xmlrpc.Fault(108, "Error in list_peers({},{})".format(key, please))
        returnValue(0)

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
