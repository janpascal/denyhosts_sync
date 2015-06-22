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

def read_config(filename):
    global dbtype, dbparams, clean_database
    global maintenance_interval, expiry_days
    global max_reported_crackers
    global logfile

    _config = ConfigParser.SafeConfigParser()
    _config.read(filename)

    dbtype = _config.get("database", "type")
    clean_database = _config.getboolean("database", "clean_database")
    dbparams = {key: value for (key,value) in _config.items("database") 
        if key != "type" and key != "clean_database"}
    if dbtype=="sqlite3":
        dbparams["check_same_thread"]=False

    maintenance_interval = _config.getint("maintenance", "interval_seconds")
    expiry_days = _config.getfloat("maintenance", "expiry_days")

    max_reported_crackers = _config.getint("sync", "max_reported_crackers")

