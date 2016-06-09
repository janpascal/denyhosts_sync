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

from denyhosts_server import config
from denyhosts_server import models
from denyhosts_server import controllers 
from denyhosts_server import database
from denyhosts_server.models import Cracker, Report

from twisted.internet.defer import inlineCallbacks, returnValue

import libnacl.public
import libnacl.utils

import base
import logging

from denyhosts_server import peering

# TODO
# What to test:
# 1. update sent to slaves get processed by slave correctly
# 2. wrong key is detected
# 3. update is sent encrypted
# 4. list_peers works correctly
# 5. check_peers works correctly

class TestPeering(base.TestBase):
    @inlineCallbacks
    def setUp(self):
        yield base.TestBase.setUp(self, "peer0.conf")
        peering.load_keys()

        # Start peer servers
        cwd = os.path.join(os.getcwd(), "..")
        print("Cleaning peer servers...")
        peer1=subprocess.Popen("PYTHONPATH=. scripts/denyhosts-server -c tests/peer1.conf --recreate-database --force", cwd=cwd, shell=True)
        peer2=subprocess.Popen("PYTHONPATH=. scripts/denyhosts-server -c tests/peer2.conf --recreate-database --force", cwd=cwd, shell=True)
        peer1.wait()
        peer2.wait()

        print("Starting peer servers...")
        self.peer1=subprocess.Popen("PYTHONPATH=. scripts/denyhosts-server -c tests/peer1.conf", cwd=cwd, shell=True)
        self.peer2=subprocess.Popen("PYTHONPATH=. scripts/denyhosts-server -c tests/peer2.conf", cwd=cwd, shell=True)

        time.sleep(3)
        yield

    def tearDown(self):
        print("Shutting down peer1...")
        self.peer1.terminate()
        print("Shutting down peer2...")
        self.peer2.terminate()

    @inlineCallbacks
    def test_send_update_to_peers(self):
        yield peering.send_update("11.11.11.11", time.time(), ["1.1.1.1", "2.2.2.2", "3.3.3.3"])
        # TODO check that the peers actually have the update

    @inlineCallbacks
    def test_list_peers(self):
        peer_url = "http://test.peer:9911"
        peer_keypair = libnacl.public.SecretKey()
        config.peers[peer_url] = peer_keypair.pk
        peering._peer_boxes[peer_url] = libnacl.public.Box(peering._own_key.sk, libnacl.public.PublicKey(peer_keypair.pk))
        box = libnacl.public.Box(peer_keypair.sk, peering._own_key.pk)
        please = box.encrypt("please")
        peer_list = yield peering.list_peers(peer_keypair.pk, please)
        print(peer_list)
        # TODO check that this is actually my own peer list
        
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
