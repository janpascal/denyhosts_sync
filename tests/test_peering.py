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

import os
import os.path
import time
import subprocess

from denyhosts_server import models
from denyhosts_server import controllers 
from denyhosts_server import database
from denyhosts_server.models import Cracker, Report

from twisted.internet.defer import inlineCallbacks, returnValue

import base
import logging

from denyhosts_server import peering

class TestPeering(base.TestBase):
    @inlineCallbacks
    def setUp(self):
        yield base.TestBase.setUp(self, "test-master.conf")

        # Start slave server
        cwd = os.path.join(os.getcwd(), "..")
        self.slave1=subprocess.Popen("PYTHONPATH=. scripts/denyhosts-server -c sqlite_slave1.conf", cwd=cwd, shell=True)
        self.slave2=subprocess.Popen("PYTHONPATH=. scripts/denyhosts-server -c sqlite_slave2.conf", cwd=cwd, shell=True)
        time.sleep(3)
        yield

    def tearDown(self):
        self.slave1.terminate()
        self.slave2.terminate()

    @inlineCallbacks
    def test_send_update_to_slaves(self):
        peering.load_keys()
        yield peering.send_update_to_slaves("11.11.11.11", ["1.1.1.1", "2.2.2.2",
        "3.3.3.3"])

        
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
