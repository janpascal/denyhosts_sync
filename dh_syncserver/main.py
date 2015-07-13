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
import signal
import sys

from twisted.web import server
from twisted.enterprise import adbapi
from twisted.internet import task, reactor
from twisted.internet.defer import inlineCallbacks, returnValue

from twistar.registry import Registry

import views
import debug_views
import models
import controllers
import config
import database

def stop_reactor(value):
    print(value)
    reactor.stop()

def sighup_handler(signum, frame):
    global configfile
    global main_xmlrpc_handler

    logging.warning("Received SIGHUP, reloading configuration file...")
    debug_was_on = config.enable_debug_methods
    old_listen_port = config.listen_port
    config.read_config(configfile)

    configure_logging()
    schedule_jobs()

    if debug_was_on and not config.enable_debug_methods:
        # Remove debug methods
        # Missing API in class XMLRPC
        del main_xmlrpc_handler.subHandlers["debug"]

    if config.enable_debug_methods and not debug_was_on:
        d = debug_views.DebugServer(main_xmlrpc_handler)
        main_xmlrpc_handler.putSubHandler('debug', d)

    if config.listen_port != old_listen_port:
        start_listening(config.listen_port)

_listener = None
def start_listening(port, interface=''):
    global _listener
    if _listener is not None:
        _listener.stopListening()
    _listener = reactor.listenTCP(port, server.Site(main_xmlrpc_handler), interface=interface)

maintenance_job = None
legacy_sync_job = None

def schedule_jobs():
    global maintenance_job, legacy_sync_job

    # Reschedule maintenance job
    if maintenance_job is not None:
        maintenance_job.stop()
    maintenance_job = task.LoopingCall(controllers.perform_maintenance)
    maintenance_job.start(config.maintenance_interval, now=False)

    # Reschedul legacy sync job
    if legacy_sync_job is not None:
        legacy_sync_job.stop()
    legacy_sync_job = task.LoopingCall(controllers.download_from_legacy_server)
    legacy_sync_job.start(config.legacy_frequency, now=False)

def configure_logging():
    # Remove all handlers associated with the root logger object.
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    # Use basic configuration
    logging.basicConfig(filename=config.logfile,
        level=config.loglevel,
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S")

def run_main():
    global configfile
    global maintenance_job, legacy_sync_job
    global main_xmlrpc_handler

    parser = argparse.ArgumentParser(description="DenyHosts sync server")
    parser.add_argument("-c", "--config", default="/etc/dh_syncserver.conf", help="Configuration file")
    parser.add_argument("--recreate-database", action='store_true', help="Wipe and recreate the database")
    parser.add_argument("--evolve-database", action='store_true', help="Evolve the database to the latest schema version")
    parser.add_argument("--purge-legacy-addresses", action='store_true',
       help="Purge all hosts downloaded from the legacy server. DO NOT USE WHEN DH_SYNCSERVER IS RUNNING!")
    parser.add_argument("--purge-reported-addresses", action='store_true',
        help="Purge all hosts that have been reported by clients. DO NOT USE WHEN DH_SYNCSERVER IS RUNNING!")
    parser.add_argument("--purge-ip", action='store',
        help="Purge ip address from both legacy and reported host lists. DO NOT USE WHEN DH_SYNCSERVER IS RUNNING!")
    parser.add_argument("-f", "--force", action='store_true',
        help="Do not ask for confirmation, execute action immediately")
    args = parser.parse_args()

    configfile = args.config

    config.read_config(args.config)

    configure_logging()

    Registry.DBPOOL = adbapi.ConnectionPool(config.dbtype, **config.dbparams)
    Registry.register(models.Cracker, models.Report, models.Legacy)

    single_shot = False

    if not args.force and (args.recreate_database
        or args.evolve_database
        or args.purge_legacy_addresses
        or args.purge_reported_addresses
        or args.recreate_database
        or args.purge_ip is not None):
        print("WARNING: do not run this method when dh_syncserver is running.")
        reply = raw_input("Are you sure you want to continue (Y/N): ")
        if not reply.upper().startswith('Y'):
            sys.exit()

    if args.recreate_database:
        single_shot = True
        database.clean_database().addCallbacks(stop_reactor, stop_reactor)

    if args.evolve_database:
        single_shot = True
        database.evolve_database().addCallbacks(stop_reactor, stop_reactor)

    if args.purge_legacy_addresses:
        single_shot = True
        controllers.purge_legacy_addresses().addCallbacks(stop_reactor, stop_reactor)

    if args.purge_reported_addresses:
        single_shot = True
        controllers.purge_reported_addresses().addCallbacks(stop_reactor, stop_reactor)

    if args.purge_ip is not None:
        single_shot = True
        controllers.purge_ip(args.purge_ip).addCallbacks(stop_reactor, stop_reactor)

    if not single_shot:
        signal.signal(signal.SIGHUP, sighup_handler)
        reactor.addSystemEventTrigger("after", "startup", database.check_database_version)

        main_xmlrpc_handler = views.Server()
        if config.enable_debug_methods:
            d = debug_views.DebugServer(main_xmlrpc_handler)
            main_xmlrpc_handler.putSubHandler('debug', d)
        start_listening(config.listen_port)

        # Set up maintenance and legacy sync jobs
        schedule_jobs()

    # Start reactor
    logging.info("Starting reactor...")
    reactor.run()

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
