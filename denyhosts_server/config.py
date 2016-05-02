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

import ConfigParser
import inspect
import logging
import os.path
import sys
import sqlite3

def _get(config, section, option, default=None):
    try:
        result = config.get(section, option)
    except ConfigParser.NoOptionError:
        result = default
    return result

def _getint(config, section, option, default=None):
    try:
        result = config.getint(section, option)
    except ConfigParser.NoOptionError:
        result = default
    return result

def _getboolean(config, section, option, default=None):
    try:
        result = config.getboolean(section, option)
    except ConfigParser.NoOptionError:
        result = default
    return result

def _getfloat(config, section, option, default=None):
    try:
        result = config.getfloat(section, option)
    except ConfigParser.NoOptionError:
        result = default
    return result

def read_config(filename):
    global dbtype, dbparams
    global maintenance_interval, expiry_days, legacy_expiry_days
    global max_reported_crackers
    global logfile
    global loglevel
    global xmlrpc_listen_host
    global xmlrpc_listen_port
    global legacy_server
    global legacy_frequency
    global legacy_threshold, legacy_resiliency
    global enable_debug_methods
    global stats_frequency
    global stats_resolve_hostnames
    global stats_listen_host
    global stats_listen_port
    global static_dir, graph_dir, template_dir

    _config = ConfigParser.SafeConfigParser()
    _config.readfp(open(filename,'r'))

    dbtype = _get(_config, "database", "type", "sqlite3")
    if dbtype not in ["sqlite3","MySQLdb"]:
        print("Database type {} not supported, exiting".format(dbtype))
        sys.exit()

    dbparams = {
        key: value 
        for (key,value) in _config.items("database") 
        if key != "type"
    }
    if dbtype=="sqlite3":
        dbparams["check_same_thread"] = False
        dbparams["detect_types"] = sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        dbparams["cp_max"] = 1
        if "database" not in dbparams:
            dbparams["database"] = "/var/lib/denyhosts-server/denyhosts.sqlite"
    elif dbtype=="MySQLdb":
        dbparams["cp_reconnect"] = True

    if "cp_max" in dbparams:
        dbparams["cp_max"] = int(dbparams["cp_max"])
    if "cp_min" in dbparams:
        dbparams["cp_min"] = int(dbparams["cp_min"])
    if "port" in dbparams:
        dbparams["port"] = int(dbparams["port"])
    if "connect_timeout" in dbparams:
        dbparams["connect_timeout"] = float(dbparams["connect_timeout"])
    if "timeout" in dbparams:
        dbparams["timeout"] = float(dbparams["timeout"])

    maintenance_interval = _getint(_config, "maintenance", "interval_seconds", 3600)
    expiry_days = _getfloat(_config, "maintenance", "expiry_days", 30)
    legacy_expiry_days = _getfloat(_config, "maintenance", "legacy_expiry_days", 30)

    max_reported_crackers = _getint(_config, "sync", "max_reported_crackers", 50)
    xmlrpc_listen_host = _get(_config, "sync", "listen_host", "")
    xmlrpc_listen_port = _getint(_config, "sync", "listen_port", 9911)
    enable_debug_methods = _getboolean(_config, "sync", "enable_debug_methods", False)
    legacy_server = _get(_config, "sync", "legacy_server", None)
    legacy_frequency = _getint(_config, "sync", "legacy_frequency", 300)
    legacy_threshold = _getint(_config, "sync", "legacy_threshold", 10)
    legacy_resiliency = _getint(_config, "sync", "legacy_resiliency", 10800)

    logfile = _get(_config, "logging", "logfile", "/var/log/denyhosts-server/denyhosts-server.log")
    loglevel = _get(_config, "logging", "loglevel", "INFO")
    try:
        loglevel = int(loglevel)
    except ValueError:
        try:
            loglevel = logging.__dict__[loglevel]
        except KeyError:
            print("Illegal log level {}".format(loglevel))
            loglevel = logging.INFO

    stats_frequency = _getint(_config, "stats", "update_frequency", 600)
    package_dir =  os.path.dirname(os.path.dirname(inspect.getsourcefile(read_config)))
    static_dir = _get(_config, "stats", "static_dir", 
        os.path.join( 
            package_dir,
            "static"))
    graph_dir = _get(_config, "stats", "graph_dir", os.path.join(static_dir, "graph"))
    template_dir = _get(_config, "stats", "template_dir", os.path.join(package_dir, "template"))
    stats_resolve_hostnames = _getboolean(_config, "stats", "resolve_hostnames", True)
    stats_listen_host = _get(_config, "stats", "listen_host", "")
    stats_listen_port = _getint(_config, "stats", "listen_port", 9911)
