#    denyhosts sync server
#    Copyright (C) 2015-2020 Jan-Pascal van Best <janpascal@vanbest.org>

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

import asyncio
import time
import logging
import random

from aiohttp import web
from aiohttp_xmlrpc import handler
import ipaddress
from tortoise.exceptions import DoesNotExist

from .exceptions import *
from . import models
from .models import Cracker, Report
from . import config
from . import controllers
from . import utils
#import stats
#import peering

logger = logging.getLogger(__name__)

class AppView(handler.XMLRPCView):
    
    async def rpc_add_hosts(self, hosts):
        request = self.request
        try:
            x_real_ip = request.headers.get("X-Real-IP")
            remote_ip = x_real_ip if x_real_ip else request.remote
            now = time.time()

            logging.info("add_hosts({}) from {}".format(hosts, remote_ip))
            await controllers.handle_report_from_client(remote_ip, now, hosts)
            ##try:
            ##    await peering.send_update(remote_ip, now, hosts)
            ##except xmlrpc.Fault as e:
            ##    raise e
            ##except Exception as e:
            ##    logging.warning("Error sending update to peers")
        except XMLRPCError as e:
            raise e
        except Exception as e:
            logger.exception("Exception in add_hosts")
            #raise FaultException(104, "Error adding hosts: {}".format(e))
            raise ErrorAddingHostsException("Error adding hosts: {}".format(e))

        return 0

    
    async def rpc_get_new_hosts(self, timestamp, threshold, hosts_added, resiliency):
        request = self.request
        try:
            x_real_ip = request.headers.get("X-Real-IP")
            remote_ip = x_real_ip if x_real_ip else request.remote

            logging.debug("get_new_hosts({},{},{},{}) from {}".format(timestamp, threshold, 
                hosts_added, resiliency, remote_ip))
            try:
                timestamp = int(timestamp)
                threshold = int(threshold)
                resiliency = int(resiliency)
            except:
                logging.warning("Illegal arguments to get_new_hosts from client {}".format(remote_ip))
                #raise FaultException(102, "Illegal parameters.")
                raise IllegalParametersException(f"Illegal parameters ({timestamp}, {threshold}, {resiliency}).")

            now = time.time()
            # refuse timestamps from the future
            if timestamp > now:
                logging.warning("Illegal timestamp to get_new_hosts from client {}".format(remote_ip))
                raise IllegalTimestampException("Illegal timestamp.")

            for host in hosts_added:
                if not utils.is_valid_ip_address(host):
                    logging.warning("Illegal host ip address {}".format(host))
                    raise IllegalIPAddressException("Illegal IP address \"{}\".".format(host))

            # TODO: maybe refuse timestamp from far past because it will 
            # cause much work? OTOH, denyhosts will use timestamp=0 for 
            # the first run!
            # TODO: check if client IP is a known cracker

            result = {}
            result['timestamp'] = str(int(time.time()))
            result['hosts'] = await controllers.get_qualifying_crackers(
                    threshold, resiliency, timestamp, 
                    config.max_reported_crackers, set(hosts_added))
            logging.debug("returning: {}".format(result))
        except XMLRPCError as e:
            raise e
        except Exception as e:
            logger.exception("Exception in xmlrpc_get_new_hosts")
            raise GetNewHostsException("Error in get_new_hosts: {}".format(str(e)))

        return result

    ### Debug XMLRPC accessible methods ###

    async def rpc_debug_list_all_hosts(self):
        if not config.enable_debug_methods:
            raise AccessDeniedException("Access denied")

        crackers = await Cracker.all()
        return [c.ip_address for c in crackers]

    async def rpc_debug_clear_all(self):
        if not config.enable_debug_methods:
            raise AccessDeniedException("Access denied")

        await controllers.purge_reported_addresses()

    async def rpc_debug_clear_ip(self, ip):
        if not config.enable_debug_methods:
            raise AccessDeniedException("Access denied")

        try:
            cracker = await Cracker.get(ip_address=ip)
            await cracker.delete()
            return True
        except DoesNotExist:
            return False

    # Concurrency test. 
    async def rpc_debug_test(self):
        if not config.enable_debug_methods:
            raise AccessDeniedException("Access denied")

        remote_ip = self.request.remote
        for hosts in [ 
            ["1.1.1.1", "2.2.2.2"],
            ["1.1.1.7", "2.2.2.8"]
            ]: 
            for i in range(5):
                now = time.time()
                task = asyncio.create_task(controllers.handle_report_from_client(remote_ip, now, hosts))

                def callback(future):
                    try:
                        _ = future.result()
                    except Exception as e:
                        logger.exception("Task in DebugServer.rpc_test() raised an exception!")
                task.add_done_callback(callback)

    # For concurrency testing. Remove before public installation!
    async def rpc_debug_maintenance(self):
        if not config.enable_debug_methods:
            raise AccessDeniedException("Access denied")

        await controllers.perform_maintenance()

    def random_ip_address(self):
        while True:
            ip = ".".join(map(str, (random.randint(0, 255) for _ in range(4))))
            if utils.is_valid_ip_address(ip):
                return ip
        
    _crackers = []
    
    async def rpc_debug_test_bulk_insert(self, count, same_crackers = False, when=None):
        if not config.enable_debug_methods:
            raise AccessDeniedException("Access denied")

        if same_crackers and len(self._crackers) < count:
            logging.debug("Filling static crackers from {} to {}".format(len(self._crackers), count))
            for i in range(len(self._crackers), count):
                self._crackers.append(self.random_ip_address())

        if when is None:
            when = time.time()

        for i in range(count):
            reporter = self.random_ip_address()
            if same_crackers:
                cracker_ip = self._crackers[i]
            else:
                cracker_ip = self.random_ip_address()

            logging.debug("Adding report for {} from {} at {}".format(cracker_ip, reporter, when))

            await utils.wait_and_lock_host(cracker_ip)
            try:
                try:
                    cracker = await Cracker.get(ip_address=cracker_ip)
                except DoesNotExist:
                    cracker = Cracker(ip_address=cracker_ip, first_time=when,
                            latest_time=when, resiliency=0, total_reports=0, current_reports=0)
                    await cracker.save()
                await controllers.add_report_to_cracker(cracker, reporter, when=when)
            finally:
                utils.unlock_host(cracker_ip)
            logging.debug("Done adding report for {} from {}".format(cracker_ip,reporter))
        total = await Cracker.all().count()
        total_reports = await Report.all().count()
        return (total,total_reports)

    async def rpc_debug_clear_bulk_cracker_list(self):
        if not config.enable_debug_methods:
            raise AccessDeniedException("Access denied")

        self._crackers = []
    
    async def rpc_debug_get_cracker_info(self, ip):
        if not config.enable_debug_methods:
            raise AccessDeniedException("Access denied")

        if not utils.is_valid_ip_address(ip):
            logging.warning("Illegal host ip address {}".format(ip))
            raise xmlrpc.Fault(101, "Illegal IP address \"{}\".".format(ip))
        #logging.info("Getting info for cracker {}".format(ip))
        try:
            cracker = await Cracker.get(ip_address=ip)
        except DoesNotExist:
            raise UnknownCrackerException("Cracker {} unknown".format(ip))

        #logging.info("found cracker: {}".format(cracker))
        #reports = await cracker.reports.all()
        ##logging.info("found reports: {}".format(reports))
        cracker_cols=['ip_address','first_time', 'latest_time', 'resiliency', 'total_reports', 'current_reports']
        report_cols=['ip_address','first_report_time', 'latest_report_time']
        return [(await Cracker.filter(ip_address=ip).values())[0], await
                cracker.reports.all().values()] 

##class WebResource(Resource):
##    #isLeaf = True
##
##    def getChild(self, name, request):
##        if name == '':
##            return self
##        return Resource.getChild(self, name, request)
##
##    def render_GET(self, request):
##        logging.debug("GET({})".format(request))
##        request.setHeader("Content-Type", "text/html; charset=utf-8")
##        def done(result):
##            if result is None:
##                request.write("<h1>An error has occurred</h1>")
##            else:
##                request.write(result.encode('utf-8'))
##            request.finish()
##        def fail(err):
##            request.processingFailed(err)
##        stats.render_stats().addCallbacks(done, fail)
##        return server.NOT_DONE_YET

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
