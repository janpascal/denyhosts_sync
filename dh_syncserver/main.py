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

import sqlite3
import time
import logging
import argparse

from twisted.web import server
from twisted.enterprise import adbapi
from twisted.internet import task
from twisted.internet.defer import inlineCallbacks, returnValue

from twistar.registry import Registry

import views
import models
import controllers
import config
import database

def stop_reactor(value):
    print(value)
    from twisted.internet import reactor
    reactor.stop()

def run_main():             
    parser = argparse.ArgumentParser(description="DenyHosts sync server")
    parser.add_argument("-c", "--config", default="/etc/dh_syncserver.conf", help="Configuration file")
    parser.add_argument("--recreate-database", action='store_true', help="Wipe and recreate the database")
    parser.add_argument("--evolve-database", action='store_true', help="Evolve the database to the latest schema version")
    args = parser.parse_args()

    config.read_config(args.config)

    logging.basicConfig(filename=config.logfile, 
        level=config.loglevel,
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S")

    Registry.DBPOOL = adbapi.ConnectionPool(config.dbtype, **config.dbparams)
    Registry.register(models.Cracker, models.Report)

    single_shot = False

    if args.recreate_database:
        single_shot = True
        database.clean_database().addCallbacks(stop_reactor, stop_reactor)

    if args.evolve_database:
        single_shot = True
        database.evolve_database().addCallbacks(stop_reactor, stop_reactor)

    from twisted.internet import reactor

    if not single_shot:
        reactor.addSystemEventTrigger("after", "startup", database.check_database_version)

        r = views.Server()
        reactor.listenTCP(config.listen_port, server.Site(r))

        # Set up maintenance job
        l = task.LoopingCall(controllers.perform_maintenance)
        l.start(config.maintenance_interval, now=False) 
        
        # Set up legacy sync job
        l = task.LoopingCall(controllers.download_from_legacy_server)
        l.start(config.legacy_frequency, now=False) 
    
    # Start reactor
    logging.info("Starting reactor...")
    logging.getLogger().handlers[0].flush()
    reactor.run()

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
