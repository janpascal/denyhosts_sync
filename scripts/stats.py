#!/usr/bin/env python

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

import argparse

from twisted.internet import task, reactor
from twisted.enterprise import adbapi
from twistar.registry import Registry

from dh_syncserver import config
from dh_syncserver import models
from dh_syncserver import database
import dh_syncserver.stats 

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="DenyHosts sync server statistics")
    parser.add_argument("-c", "--config", default="/etc/dh_syncserver.conf", help="Configuration file")
    args = parser.parse_args()

    configfile = args.config

    config.read_config(args.config)

    Registry.DBPOOL = adbapi.ConnectionPool(config.dbtype, **config.dbparams)
    Registry.register(models.Cracker, models.Report, models.Legacy)

    reactor.callLater(0, dh_syncserver.stats.create_stats_page, True)
    reactor.run()

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
