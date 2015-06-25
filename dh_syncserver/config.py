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
    global dbtype, dbparams, clean_database
    global maintenance_interval, expiry_days
    global max_reported_crackers
    global logfile
    global listen_port
    global legacy_server

    _config = ConfigParser.SafeConfigParser()
    _config.read(filename)

    dbtype = _get(_config, "database", "type", "sqlite3")
    clean_database = _getboolean(_config, "database", "clean_database", False)
    dbparams = {
        key: value 
        for (key,value) in _config.items("database") 
        if key != "type" and key != "clean_database"
    }
    if dbtype=="sqlite3":
        dbparams["check_same_thread"]=False
        if "database" not in dbparams:
            dbparams["database"] = "/var/lib/dh_syncserver/denyhosts.sqlite"

    maintenance_interval = _getint(_config, "maintenance", "interval_seconds", 3600)
    expiry_days = _getfloat(_config, "maintenance", "expiry_days", 30)

    max_reported_crackers = _getint(_config, "sync", "max_reported_crackers", 50)
    listen_port = _getint(_config, "sync", "listen_port", 9911)
    legacy_server = _get(_config, "sync", "legacy_server", "http://xmlrpx.denyhosts.net:9911")

    logfile = _get(_config, "logging", "logfile", "/var/log/dh-syncserver.log")
