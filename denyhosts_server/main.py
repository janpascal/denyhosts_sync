# denyhosts sync server
# Copyright (C) 2015-2016 Jan-Pascal van Best <janpascal@vanbest.org>

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

import argparse
import logging
import signal
import sys
import ConfigParser

from twisted.web import server, resource, static
from twisted.enterprise import adbapi
from twisted.internet import task, reactor
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.python import log

from twistar.registry import Registry

import views
import debug_views
import peering_views
import models
import controllers
import config
import database
import stats
import utils
import peering

import __init__

def stop_reactor(value):
    print(value)
    reactor.stop()

def sighup_handler(signum, frame):
    global configfile
    global main_xmlrpc_handler

    logging.warning("Received SIGHUP, reloading configuration file...")
    debug_was_on = config.enable_debug_methods
    old_xmlrpc_listen_port = config.xmlrpc_listen_port
    old_stats_listen_port = config.stats_listen_port
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

    stop_listening().addCallback(lambda _: start_listening())

@inlineCallbacks
def shutdown():
    global main_xmlrpc_handler
    global _xmlrpc_listener
    global _xmlrpc_site
    try:
        site = _xmlrpc_site
        logging.info("shutting down, first closing listening ports...")
        print("Shutting down, hold on a moment...")
        yield stop_listening()

# This doesn't work, site.session is always empty
        logging.info("Ports closed, waiting for current sessions to close...")
        logging.debug("Clients still connected: {}".format(len(site.sessions)))
        while not len(site.sessions)==0:
            logging.debug("Waiting, {} sessions still active".format(len(site.sessions)))
            yield task.deferLater(reactor, 1, lambda _:0, 0)

        logging.info("No more sessions, waiting for locked hosts...")
        while not utils.none_waiting():
            logging.info("Waiting to shut down, {} hosts still blocked".format(utils.count_waiting()))
            yield task.deferLater(reactor, 1, lambda _:0, 0)
            logging.debug("reactor.getDelayedCalls: {}".format([c.func for c in reactor.getDelayedCalls()]))

        logging.info("All hosts unlocked, waiting 3 more seconds...")
        yield task.deferLater(reactor, 1, lambda _:0, 0)
        logging.debug("Waiting 2 more seconds...")
        yield task.deferLater(reactor, 1, lambda _:0, 0)
        logging.debug("Waiting 1 more second...")
        yield task.deferLater(reactor, 1, lambda _:0, 0)
        logging.info("Continuing shutdown")
    except:
        logging.exception("Error in shutdown callback")
    
_xmlrpc_listener = None
_stats_listener = None
_xmlrpc_site = None

# Returns a callback. Wait on it before the port(s) are actually closed
def stop_listening():
    logging.debug("main.stop_listening()")
    global _xmlrpc_listener
    global _stats_listener
    global _xmlrpc_site

    # It's not easy to actually close a listening port.
    # You need to close both the port and the protocol,
    # and wait for them
    if _xmlrpc_listener is not None:
        deferred = _xmlrpc_listener.stopListening()
        deferred.addCallback(_xmlrpc_listener.loseConnection)
    else:
        deferred = Deferred()

    if _stats_listener is not None:
        deferred.addCallback(_stats_listener.stopListening)
        deferred.addCallback(_stats_listener.loseConnection)

    _xmlrpc_listener = None
    _stats_listener = None
    _xmlrpc_site = None

    return deferred

def start_listening():
    logging.debug("main.start_listening()")
    global _xmlrpc_listener
    global _xmlrpc_site
    global _stats_listener
    global main_xmlrpc_handler

    # Configure web resources
    main_xmlrpc_handler = views.Server()
    stats_resource = views.WebResource()
    web_static = static.File(config.static_dir)
    static.File.contentTypes['.svg'] = 'image/svg+xml'
    web_graphs = static.File(config.graph_dir)

    # Roots
    if config.stats_listen_port == config.xmlrpc_listen_port:
        xmlrpc_root = stats_resource
    else:
        xmlrpc_root = resource.Resource()
    stats_root = stats_resource

    # /RPC2
    xmlrpc_root.putChild('RPC2', main_xmlrpc_handler)

    # Peering handler
    p = peering_views.PeeringServer(main_xmlrpc_handler)
    main_xmlrpc_handler.putSubHandler('peering', p)

    # xmlrpc debug handler
    if config.enable_debug_methods:
        d = debug_views.DebugServer(main_xmlrpc_handler)
        main_xmlrpc_handler.putSubHandler('debug', d)

    # /static
    stats_root.putChild('static', web_static)
    # /static/graphs
    web_static.putChild('graphs', web_graphs)

    logging.info("Start listening on host:port {}:{}".format(config.xmlrpc_listen_address, config.xmlrpc_listen_port))
    _xmlrpc_site = server.Site(xmlrpc_root)
    _xmlrpc_listener = reactor.listenTCP(config.xmlrpc_listen_port, _xmlrpc_site, interface=config.xmlrpc_listen_address)

    if config.stats_listen_port == config.xmlrpc_listen_port and config.xmlrpc_listen_address == config.stats_listen_address:
        _stats_listener = None
    else:
        logging.info("Start serving statistics on host:port {}:{}".format(config.stats_listen_address, config.stats_listen_port))
        _stats_listener = reactor.listenTCP(config.stats_listen_port, server.Site(stats_root), interface=config.stats_listen_address)

maintenance_job = None
legacy_sync_job = None
stats_job = None

def schedule_jobs():
    global maintenance_job, legacy_sync_job, stats_job

    # Reschedule maintenance job
    if maintenance_job is not None:
        maintenance_job.stop()
    maintenance_job = task.LoopingCall(controllers.perform_maintenance)
    maintenance_job.start(config.maintenance_interval, now=False)

    # Reschedule legacy sync job
    if legacy_sync_job is not None:
        legacy_sync_job.stop()
    legacy_sync_job = task.LoopingCall(controllers.download_from_legacy_server)
    legacy_sync_job.start(config.legacy_frequency, now=False)

    # Reschedule stats job
    if stats_job is not None:
        stats_job.stop()
    stats_job = task.LoopingCall(stats.update_stats_cache)
    stats_job.start(config.stats_frequency, now=True)

def configure_logging():
    # Remove all handlers associated with the root logger object.
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    # Use basic configuration
    logging.basicConfig(filename=config.logfile,
        level=config.loglevel,
        format="%(asctime)s %(module)-8s %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S")

    # Collect Twisted log messages in Python logging system
    observer = log.PythonLoggingObserver()
    observer.start()

def run_main():
    global configfile
    global maintenance_job, legacy_sync_job
    global main_xmlrpc_handler, stats_resource, web_root, web_static

    parser = argparse.ArgumentParser(description="DenyHosts sync server")
    parser.add_argument("-c", "--config", default="/etc/denyhosts-server.conf", help="Configuration file")
    parser.add_argument("--recreate-database", action='store_true', help="Wipe and recreate the database")
    parser.add_argument("--evolve-database", action='store_true', help="Evolve the database to the latest schema version")
    parser.add_argument("--purge-legacy-addresses", action='store_true',
       help="Purge all hosts downloaded from the legacy server. DO NOT USE WHEN DENYHOSTS-SERVER IS RUNNING!")
    parser.add_argument("--purge-reported-addresses", action='store_true',
        help="Purge all hosts that have been reported by clients. DO NOT USE WHEN DENYHOSTS-SERVER IS RUNNING!")
    parser.add_argument("--purge-ip", action='store',
        help="Purge ip address from both legacy and reported host lists. DO NOT USE WHEN DENYHOSTS-SERVER IS RUNNING!")
    parser.add_argument("--check-peers", action="store_true", 
        help="Check if all peers are responsive, and if they agree about the peer list")
    parser.add_argument("--bootstrap-from-peer", action="store", metavar="PEER_URL",
        help="First wipe database and then bootstrap database from peer. DO NOT USE WHEN DENYHOSTS-SERVER IS RUNNING!")
    parser.add_argument("-f", "--force", action='store_true',
        help="Do not ask for confirmation, execute action immediately")
    args = parser.parse_args()

    configfile = args.config

    try:
        config.read_config(args.config)
    except ConfigParser.NoSectionError, e:
        print("Error in reading the configuration file from \"{}\": {}.".format(args.config, e))
        print("Please review the configuration file. Look at the supplied denyhosts-server.conf.example for more information.")
        sys.exit()

    configure_logging()

    peering.load_keys()

    Registry.DBPOOL = adbapi.ConnectionPool(config.dbtype, **config.dbparams)
    Registry.register(models.Cracker, models.Report, models.Legacy)

    single_shot = False

    if not args.force and (args.recreate_database
        or args.evolve_database
        or args.purge_legacy_addresses
        or args.purge_reported_addresses
        or args.recreate_database
        or args.bootstrap_from_peer
        or args.purge_ip is not None):
        print("WARNING: do not run this method when denyhosts-server is running.")
        reply = raw_input("Are you sure you want to continue (Y/N): ")
        if not reply.upper().startswith('Y'):
            sys.exit()

    if args.check_peers:
        if peering.check_peers():
            sys.exit(0)
        else:
            sys.exit(1)

    if args.recreate_database:
        single_shot = True
        database.clean_database().addCallbacks(stop_reactor, stop_reactor)

    if args.evolve_database:
        single_shot = True
        database.evolve_database().addCallbacks(stop_reactor, stop_reactor)

    if args.bootstrap_from_peer:
        single_shot = True
        peering.bootstrap_from(args.bootstrap_from_peer).addCallbacks(stop_reactor, stop_reactor)

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
        reactor.addSystemEventTrigger("before", "shutdown", shutdown)

        start_listening()

        # Set up maintenance and legacy sync jobs
        schedule_jobs()

    # Start reactor
    logging.info("Starting denyhosts-server version {}".format(__init__.version))
    reactor.run()

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
