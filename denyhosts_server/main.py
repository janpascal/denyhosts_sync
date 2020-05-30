#!/usr/bin/env python3

# denyhosts sync server
# Copyright (C) 2015-2020 Jan-Pascal van Best <janpascal@vanbest.org>

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
import asyncio
import logging
import os
import signal
import sys
import configparser

from aiohttp import web
import aiohttp_jinja2
import jinja2
from tortoise import Tortoise

from . import views
##import debug_views
#import peering_views
from . import models
from . import controllers
from . import config
from . import database
from . import exceptions
from . import stats
from . import utils
#from . import peering

from . import __init__

logger = logging.getLogger(__name__)

## def sighup_handler(signum, frame):
##     global configfile
##     global main_xmlrpc_handler
## 
##     logging.warning("Received SIGHUP, reloading configuration file...")
##     debug_was_on = config.enable_debug_methods
##     old_xmlrpc_listen_port = config.xmlrpc_listen_port
##     old_stats_listen_port = config.stats_listen_port
##     config.read_config(configfile)
## 
##     configure_logging()
##     schedule_jobs()
## 
##     if debug_was_on and not config.enable_debug_methods:
##         # Remove debug methods
##         # Missing API in class XMLRPC
##         del main_xmlrpc_handler.subHandlers["debug"]
## 
##     if config.enable_debug_methods and not debug_was_on:
##         d = debug_views.DebugServer(main_xmlrpc_handler)
##         main_xmlrpc_handler.putSubHandler('debug', d)
## 
##     stop_listening().addCallback(lambda _: start_listening())


# TODO is this still necessary with aiohttp?
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
            logging.info("Waiting to shut down, {} hosts still locked".format(utils.count_waiting()))
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
## def stop_listening():
##     logging.debug("main.stop_listening()")
##     global _xmlrpc_listener
##     global _stats_listener
##     global _xmlrpc_site
## 
##     # It's not easy to actually close a listening port.
##     # You need to close both the port and the protocol,
##     # and wait for them
##     if _xmlrpc_listener is not None:
##         deferred = _xmlrpc_listener.stopListening()
##         deferred.addCallback(_xmlrpc_listener.loseConnection)
##     else:
##         deferred = Deferred()
## 
##     if _stats_listener is not None:
##         deferred.addCallback(_stats_listener.stopListening)
##         deferred.addCallback(_stats_listener.loseConnection)
## 
##     _xmlrpc_listener = None
##     _stats_listener = None
##     _xmlrpc_site = None
## 
##     return deferred

#maintenance_job = None
#stats_job = None

async def start_listening():
    app = create_app()

    logging.debug("main.start_listening()")

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, port=config.xmlrpc_listen_port)
    await site.start()

# wait for finish signal
# TODO move somewhere else :)
# await runner.cleanup()

##    global _xmlrpc_listener
##    global _xmlrpc_site
##    global _stats_listener
##    global main_xmlrpc_handler
##
##    # Configure web resources
##    main_xmlrpc_handler = views.Server()
##    stats_resource = views.WebResource()
##    web_static = static.File(config.static_dir)
##    static.File.contentTypes['.svg'] = 'image/svg+xml'
##    web_graphs = static.File(config.graph_dir)
##
##    # Roots
##    if config.stats_listen_port == config.xmlrpc_listen_port:
##        xmlrpc_root = stats_resource
##    else:
##        xmlrpc_root = resource.Resource()
##    stats_root = stats_resource
##
##    # /RPC2
##    xmlrpc_root.putChild('RPC2', main_xmlrpc_handler)
##
##    # Peering handler
##    p = peering_views.PeeringServer(main_xmlrpc_handler)
##    main_xmlrpc_handler.putSubHandler('peering', p)
##
##    # xmlrpc debug handler
##    if config.enable_debug_methods:
##        d = debug_views.DebugServer(main_xmlrpc_handler)
##        main_xmlrpc_handler.putSubHandler('debug', d)
##
##    # /static
##    stats_root.putChild('static', web_static)
##    # /static/graphs
##    web_static.putChild('graphs', web_graphs)

##    logging.info("Start listening on port {}".format(config.xmlrpc_listen_port))
##    _xmlrpc_site = server.Site(xmlrpc_root)
##    _xmlrpc_listener = reactor.listenTCP(config.xmlrpc_listen_port, _xmlrpc_site)
##
##    if config.stats_listen_port == config.xmlrpc_listen_port:
##        _stats_listener = None
##    else:
##        logging.info("Start serving statistics on port {}".format(config.stats_listen_port))
##        _stats_listener = reactor.listenTCP(config.stats_listen_port, server.Site(stats_root))

def configure_logging():
    # Remove all handlers associated with the root logger object.
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    # Use basic configuration
    logging.basicConfig(filename=config.logfile,
        level=config.loglevel,
        format="%(asctime)s %(name)-16s %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S")

    logging.getLogger('aiosqlite').setLevel(logging.INFO)
    logging.getLogger('db_client').setLevel(logging.INFO)
    logging.getLogger('matplotlib.font_manager').setLevel(logging.INFO)

async def init_database(app):
    # TODO
    #peering.load_keys()

    ## TODO: configurate database from configuration
    db_config = {
        'connections': {
            # Dict format for connection
            'default': {
                'engine': 'tortoise.backends.sqlite',
                'credentials': {
                    'file_path': 'db.sqlite3',
                }
            }
        },
        'apps': {
            'models': {
                'models': ['denyhosts_server.models'],
                # If no default_connection specified, defaults to 'default'
                'default_connection': 'default',
            }
        }
    }

    logger.debug("Configuring Tortoise-orm from db_config...")
    await Tortoise.init(config=db_config)
    #    db_url='sqlite://db.sqlite3',
    #    modules={'models': ['denyhosts_server.models']}
    #)


    logger.debug(f"Tortoise _connections: {Tortoise._connections}")

async def start_jobs(app): 
    # Reschedule maintenance job
    if 'maintenance_job' in app:
        await app['maintenance_job'].stop()
    app['maintenance_job'] = utils.PeriodicJob(config.maintenance_interval, controllers.perform_maintenance)
    await app['maintenance_job'].start()

    # Reschedule stats job
    if 'stats_job' in app:
        await app['stats_job'].stop()
    app['stats_job'] = utils.PeriodicJob(config.stats_frequency, stats.update_stats_cache)
    await app['stats_job'].start()

async def stop_jobs(app):
    logger.info("Stopping periodic jobs...")
    # Stop maintenance job
    if 'maintenance_job' in app:
        await app['maintenance_job'].stop(timeout=30)

    # Stop stats job
    if 'stats_job' in app:
        await app['stats_job'].stop(timeout=30)

async def shutdown_database(app):
    await Tortoise.close_connections()

def create_app(arg_configfile=None):
    global configfile

    if arg_configfile is None:
        configfile = os.environ.get('DENYHOSTS_SERVER_CONF', '/etc/denyhosts-server.conf')
    else:
        configfile = arg_configfile

    print(f"Creating denyhosts-server app from config file {configfile}")

    try:
        config.read_config(configfile)
    except Exception as e:
        print("Error in reading the configuration file from \"{}\": {}.".format(configfile, e))
        print("Set the DENYHOSTS_SERVER_CONF enviromenment variable to change the configuration file location.")
        print("Please review the configuration file. Look at the supplied denyhosts-server.conf.example for more information.")
        raise Exception(f"Failed to read {configfile}")

    configure_logging()
    exceptions.register_exceptions()

    app = web.Application()
    app.router.add_view('/RPC2', views.AppView)
    app.router.add_view('/', views.stats_view)
    app.router.add_static('/static/graphs', config.graph_dir)
    app.router.add_static('/static', config.static_dir)

    app.on_startup.append(init_database)
    app.on_startup.append(start_jobs)
    app.on_shutdown.append(stop_jobs)
    app.on_cleanup.append(shutdown_database)

    logger.debug(f"Template dir: {config.template_dir}")
    aiohttp_jinja2.setup(app,
        loader=jinja2.FileSystemLoader(config.template_dir),
        filters={
            'datetime': stats.format_datetime
            })

    return app

async def run_action(action, *args):
    await init_database(None)

    if action == "recreate-database":
        await database.clean_database()
    elif action == "evolve-database":
        print("evolve-database not supported yet")
        # await database.evolve_database()
    elif action == "bootstrap-from-peer":
        print("peering not supported yet")
        #await peering.bootstrap_from(args[0])
    elif action == "purge-reported-addresses":
        await controllers.purge_reported_addresses()
    elif action == "recalculate-history":
        print("Clearing history...")
        await stats.clear_history()
        print("Recalculating history...")
        await stats.update_recent_history()
        await stats.update_country_history()
    elif action == "purge-ip":
        await controllers.purge_ip(args[0])
    elif action == "check-peers":
        print("peering not supported yet")
        #if await peering.check_peers():
        #    sys.exit(0)
        #else:
        #    sys.exit(1)

    await shutdown_database(None)

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
