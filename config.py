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
    global dbtype, dbparams
    global maintenance_interval, expiry_days

    _config = ConfigParser.SafeConfigParser()
    _config.read(filename)

    dbtype = _config.get("database", "type")
    dbparams = {key: value for (key,value) in _config.items("database") if key != "type"}
    if dbtype=="sqlite3":
        dbparams["check_same_thread"]=False

    maintenance_interval = _config.getint("maintenance", "interval_seconds")
    expiry_days = _config.getfloat("maintenance", "expiry_days")

