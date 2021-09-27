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

import json
import os
import os.path
import signal
import time
import subprocess

from xmlrpc.client import ServerProxy

from denyhosts_server import config
from denyhosts_server import models
from denyhosts_server import controllers 
from denyhosts_server import database
from denyhosts_server import version as server_version
from denyhosts_server.models import Cracker, Report
from denyhosts_server import peering

from twisted.internet import reactor, task
from twisted.internet.defer import inlineCallbacks, returnValue
from  twisted.python import log

import libnacl.public
import libnacl.utils

from . import base
import logging


class TestPeering(base.TestBase):
    @inlineCallbacks
    def setUp(self):
        yield base.TestBase.setUp(self, "peer0.conf")
        peering.load_keys()

        # Start peer servers
        cwd = os.path.join(os.getcwd(), "..")
        log.msg("Cleaning peer servers...")
        peer1=subprocess.Popen("PYTHONPATH=. scripts/denyhosts-server -c tests/peer1.conf --recreate-database --force > /dev/null 2>&1", cwd=cwd, shell=True)
        peer2=subprocess.Popen("PYTHONPATH=. scripts/denyhosts-server -c tests/peer2.conf --recreate-database --force > /dev/null 2>&1", cwd=cwd, shell=True)
        peer1.wait()
        peer2.wait()

        log.msg("Starting peer servers...")
        self.peer1=subprocess.Popen("PYTHONPATH=. scripts/denyhosts-server -c tests/peer1.conf >/dev/null 2>&1", cwd=cwd, shell=True, preexec_fn=os.setsid)
        self.peer2=subprocess.Popen("PYTHONPATH=. scripts/denyhosts-server -c tests/peer2.conf >/dev/null 2>&1", cwd=cwd, shell=True, preexec_fn=os.setsid)

        log.msg("Waiting until peer servers are responsive...")
        for peer_url in config.peers:
            server = ServerProxy(peer_url)
            is_up = False
            start_time = time.time()
            while not is_up and time.time() - start_time < 10:
                try:
                    server.get_new_hosts(time.time(), 1, [], 3600)
                    is_up = True
                    log.msg("Peer {} is up!".format(peer_url))
                except:
                    time.sleep(0.2)
            if not is_up:
                # Try to stop the server in case they are started to leave with a clean environment
                self.tearDown()
                self.fail("Failed to start peer {}".format(peer_url))

    def tearDown(self):
        log.msg("Shutting down peer1...")
        os.killpg(self.peer1.pid, signal.SIGTERM)
        log.msg("Shutting down peer2...")
        os.killpg(self.peer2.pid, signal.SIGTERM)

        log.msg("Waiting for peers to shut down...")
        self.peer1.wait()
        self.peer2.wait()

        log.msg("Peers shut down")

    @inlineCallbacks
    def test_send_update_to_peers(self):
        yield peering.send_update("11.11.11.11", time.time(), ["1.1.1.1"])
        yield task.deferLater(reactor, 1.0, lambda _:0, 0)
        for peer_url in config.peers:
            server = ServerProxy(peer_url)
            response = server.get_new_hosts(time.time() - 15, 1, [], 0)
            log.msg("Peer {} has new hosts {}".format(peer_url, response))
            self.assertIn("1.1.1.1", response["hosts"], "Peer did not receive hosts!")

    @inlineCallbacks
    def _test_with_key(self, keypair, public_key):
        box = libnacl.public.Box(keypair.sk, peering._own_key.pk)

        data = {
            "client_ip": "11.11.11.11",
            "timestamp": time.time(),
            "hosts": ["1.1.1.1"]
        }
        data_json = json.dumps(data)
        crypted = box.encrypt(data_json)
        base64 = crypted.encode('base64')
        yield peering.handle_update(public_key, crypted)

    def _insert_peer(self):
        peer_url = "http://test.peer:9911"
        peer_keypair = libnacl.public.SecretKey()
        config.peers[peer_url] = peer_keypair.pk
        peering._peer_boxes[peer_url] = libnacl.public.Box(peering._own_key.sk, libnacl.public.PublicKey(peer_keypair.pk))
        return peer_keypair

    @inlineCallbacks
    def test_unknown_key(self):
        keypair = self._insert_peer()
        log.msg("Testing whether message from known keypair is accepted")
        yield self._test_with_key(keypair, keypair.pk)
        log.msg("Testing whether message from unknown keypair is rejected")
        unknown_keypair = libnacl.public.SecretKey()
        yield self.assertFailure(self._test_with_key(unknown_keypair, unknown_keypair.pk), Exception) 
        log.msg("Testing whether message with seemingly valid key but signed by unknown keypair is rejected")
        unknown_keypair = libnacl.public.SecretKey()
        yield self.assertFailure(self._test_with_key(unknown_keypair, keypair.pk), Exception) 

    @inlineCallbacks
    def test_list_peers(self):
        peer_keypair = self._insert_peer()
        box = libnacl.public.Box(peer_keypair.sk, peering._own_key.pk)
        please = box.encrypt("please")
        response = yield peering.list_peers(peer_keypair.pk, please)
        log.msg(response)
        peer_list = response["peers"]
        self.assertEqual(len(peer_list), len(config.peers), "Peer list not correct length")
        self.assertEqual(response["server_version"], server_version, "Incorrect server version in response")
        for peer_url in config.peers:
            self.assertIn(peer_url, peer_list, "Peer missing from received list")
            self.assertEqual(config.peers[peer_url].encode('hex'), peer_list[peer_url], "Wrong key in received peer list")

    def test_check_peers(self):
        result = peering.check_peers()
        self.assertEqual(result, True, "Check peers should be successful for default config")

        # TODO: check case where one of the peers doesn't know another peer, or has a wrong key for it

    def test_check_peers_missing(self):
        # check case where one of the peers has an extra peer that I don't know about
        # Remove one of the peers from my list
        peer_to_remove = config.peers.keys()[0]
        del config.peers[peer_to_remove]
        del peering._peer_boxes[peer_to_remove]

        result = peering.check_peers()
        self.assertEqual(result, False, "Check peers should fail if a peer is missing from my own config")

    def test_check_peers_extra(self):
        self._insert_peer()

        result = peering.check_peers()
        self.assertEqual(result, False, "Check peers should fail if one of my peers does not exist")

    def test_check_peers_wrong_own_key(self):
        config.key_file = "../tests/peer_unknown.key"
        peering.load_keys()

        result = peering.check_peers()
        self.assertEqual(result, False, "Check peers should fail if peers do not know me")
        
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
