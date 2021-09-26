# denyhosts sync server
# Copyright (C) 2016 Jan-Pascal van Best <janpascal@vanbest.org>

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

from __future__ import print_function
import logging
import json
import os.path
import sys
from xmlrpc.client import ServerProxy

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet.threads  import deferToThread

import libnacl.public
import libnacl.utils

from . import version
from . import config
from . import controllers
from . import database
from .models import Cracker, Report
from . import utils

_own_key = None

@inlineCallbacks
def send_update(client_ip, timestamp, hosts):
    for peer in config.peers:
        logging.debug("Sending update to peer {}".format(peer))
        data = {
            "client_ip": client_ip,
            "timestamp": timestamp,
            "hosts": hosts
        }
        data_json = json.dumps(data)
        crypted = _peer_boxes[peer].encrypt(data_json)
        base64 = crypted.encode('base64')

        try:
            server = yield deferToThread(ServerProxy, peer)
            yield deferToThread(server.peering.update, _own_key.pk.encode('hex'), base64)
        except:
            logging.warning("Unable to send update to peer {}".format(peer))

def decrypt_message(peer_key, message):
    peer = None
    for _peer in config.peers:
        if config.peers[_peer] == peer_key:
            peer = _peer
            break
    if peer is None:
        logging.warning("Got message from unknown peer with key {}".format(peer_key.encode('hex')))
        raise Exception("Unknown key {}".format(peer_key.encode('hex')))

    # Critical point: use our own key, instead of the one supplied by the peer
    message = _peer_boxes[peer].decrypt(message)
    return message

@inlineCallbacks
def handle_update(peer_key, update):
    json_data = decrypt_message(peer_key, update)
    data = json.loads(json_data)

    hosts = data["hosts"]
    client_ip = data["client_ip"]
    timestamp = data["timestamp"]

    yield controllers.handle_report_from_client(client_ip, timestamp, hosts)

@inlineCallbacks
def handle_schema_version(peer_key, please):
    data = decrypt_message(peer_key, please)

    if data != "please":
        logging.warning("Request for schema_version is something else than please: {}".format(data))
        raise Exception("Illegal request {}".format(data))

    schema_version = yield database.get_schema_version()

    returnValue(schema_version)

@inlineCallbacks
def handle_all_hosts(peer_key, please):
    data = decrypt_message(peer_key, please)

    if data != "please":
        logging.warning("Request for all_hosts is something else than please: {}".format(data))
        raise Exception("Illegal request {}".format(data))

    crackers = yield database.dump_crackers()

    logging.debug("Sending addresses of {} crackers to peer".format(len(crackers)))
    logging.debug("Crackers: ".format(crackers))
    
    returnValue(crackers)

@inlineCallbacks
def handle_all_reports_for_host(peer_key, host):
    host = decrypt_message(peer_key, host)

    logging.debug("peering.handle_all_reports_for_host({})".format(host))

    if not utils.is_valid_ip_address(host):
        logging.warning("Illegal IP address for all_reports_for_host: {}".format(host))
        raise Exception("Illegal request {}".format(host))

    reports = yield database.dump_reports_for_cracker(host)

    if reports is None:
        reports = []

    #logging.debug("all_reports for {}: {}".format(host, reports))
    returnValue(reports)

@inlineCallbacks
def handle_dump_table(peer_key, table):
    table = decrypt_message(peer_key, table)

    logging.debug("peering.handle_dump_table({})".format(table))

    if table not in [ "info", "legacy", "history", "country_history" ]:
        logging.warning("Illegal table for dump_table: {}".format(table))
        raise Exception("Illegal request {}".format(table))

    rows = yield database.dump_table(table)

    if rows is None:
        rows = []

    returnValue(rows)

def list_peers(peer_key, please):
    data = decrypt_message(peer_key, please)

    if data != "please":
        logging.warning("Request for list_peers is something else than please: {}".format(data))
        raise Exception("Illegal request {}".format(data))

    return {
            "server_version": version,
            "peers": {
                peer: config.peers[peer].encode('hex') 
                for peer in config.peers
            }
    }

@inlineCallbacks
def bootstrap_from(peer_url):
    crypted = _peer_boxes[peer_url].encrypt("please")
    please_base64 = crypted.encode('base64')

    server = yield deferToThread(ServerProxy, peer_url)
    remote_schema = yield server.peering.schema_version(_own_key.pk.encode('hex'), please_base64)

    print("Initializing database...")
    yield database.clean_database()

    local_schema = yield database.get_schema_version()

    if remote_schema != local_schema:
        raise Exception("Unable to bootstrap from {}: remote database schema version is {}, local {}".format(peer_url, remote_schema, local_schema))

    logging.debug("Remote database schema: {}; local schema: {}".format(remote_schema, local_schema))

    hosts = yield deferToThread(server.peering.all_hosts, _own_key.pk.encode('hex'), please_base64)

    #logging.debug("Hosts from peer: {}".format(hosts))
    print("Copying data of {} hosts from peer".format(len(hosts)), end="")

    count = 0
    for host in hosts:
        if count%100 == 0:
            print(".", end="")
            sys.stdout.flush()
        count += 1
        yield database.bootstrap_cracker(host)

        host_ip = host[1]

        crypted = _peer_boxes[peer_url].encrypt(host_ip)
        base64 = crypted.encode('base64')
        response = yield deferToThread(server.peering.all_reports_for_host, _own_key.pk.encode('hex'), base64)
        #logging.debug("All reports response: {}".format(response))

        for r in response:
            database.bootstrap_report(r)
    print(" Done")

    for table in [ "info", "legacy", "history", "country_history" ]:
        print("Copying {} table from peer...".format(table))
        crypted = _peer_boxes[peer_url].encrypt(table)
        base64 = crypted.encode('base64')
        rows = yield deferToThread(server.peering.dump_table, _own_key.pk.encode('hex'), base64)
        for row in rows:
            database.bootstrap_table(table, row)

def load_keys():
    global _own_key
    global _peer_boxes

    try:
        _own_key = libnacl.utils.load_key(config.key_file)
    except:
        logging.info("No private key yet, creating one in {}".format(config.key_file))
        _own_key = libnacl.public.SecretKey()
        _own_key.save(config.key_file)

    _peer_boxes = {
        peer: 
        libnacl.public.Box(_own_key.sk, libnacl.public.PublicKey(config.peers[peer]))
        for peer in config.peers
    }

    logging.debug("Configured peers: {}".format(config.peers))

def check_peers():
    """ Connect to all configured peers. Check if they are reachable, and if their
    list of peers and associated keys conforms to mine """
    success = True
    for peer in config.peers:
        print("Examining peer {}...".format(peer))
        peer_server = ServerProxy(peer)
        try:
            response = peer_server.list_peers(_own_key.pk.encode('hex'), _peer_boxes[peer].encrypt('please').encode('base64'))
        except Exception as e:
            print("Error requesting peer list from {} (maybe it's down, or it doesn't know my key!)".format(peer))
            print("Error message: {}".format(e))
            success = False
            continue

        print("    Peer version: {}".format(response["server_version"]))
        peer_list = response["peers"]

        # peer list should contain all the peers I know, except for the peer I'm asking, but including myself
        seen_peers = set()
        for other_peer in config.peers:
            if other_peer == peer:
                continue
            if other_peer not in peer_list:
                print("    Peer {} does not know peer {}!".format(peer, other_peer))
                success = False
                continue
            if config.peers[other_peer] != peer_list[other_peer].decode('hex'):
                print("    Peer {} knows peer {} but with key {} instead of {}!".format(peer, other_peer, peer_list[other_peer], config.peers[other_peer].encode('hex')))
                success = False
                continue
            print("    Common peer (OK): {}".format(other_peer))
            seen_peers.add(other_peer)

        # Any keys not seen should be my own
        own_key_seen = False
        for other_peer in peer_list:
            if other_peer in seen_peers:
                continue
            if peer_list[other_peer].decode('hex') == _own_key.pk:
                own_key_seen = True
                print("    Peer {} knows me as {} (OK)".format(peer, other_peer))
                continue
            print("    Peer {} knows about (to me) unknown peer {} with key {}!".format(peer, other_peer, peer_list[other_peer]))
            success = False

        if not own_key_seen:
            print("    Peer {} does not know about me!")
            success = False

    if success:
        print("All peer servers configured correctly")
    else:
        print("Inconsistent peer server configuration, check all configuration files!")

    return success

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
