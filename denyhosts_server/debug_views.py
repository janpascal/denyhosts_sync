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

import models
from models import Cracker, Report
import config
import controllers
from exceptions import *
import utils
import views

class DebugServer(handler.XMLRPCView):
    """
    Debug xmlrpc methods
    """

    async def rpc_list_all_hosts(self):
        crackers = await Cracker.all()
        return [c.ip_address for c in crackers]

    async def rpc_clear_all():
        await controllers.purge_reported_addresses()

    # Concurrency test. 
    async def rpc_test(self):
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
    async def rpc_maintenance(self):
        await controllers.perform_maintenance()

    def random_ip_address(self):
        while True:
            ip = ".".join(map(str, (random.randint(0, 255) for _ in range(4))))
            if utils.is_valid_ip_address(ip):
                return ip
        
    _crackers = []
    
    async def rpc_test_bulk_insert(self, count, same_crackers = False, when=None):
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

    async def rpc_clear_bulk_cracker_list(self):
        self._crackers = []
    
    async def rpc_get_cracker_info(self, ip):
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

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
