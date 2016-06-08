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

import logging
import json
import os.path
from xmlrpclib import ServerProxy

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet.threads  import deferToThread

import libnacl.public
import libnacl.utils

import config

_own_key = None

def send_update(originating_ip, hosts):
    if config.is_master:
        send_update_to_slaves(originating_ip, hosts)
    else:
        send_update_to_master(originating_ip, hosts)

@inlineCallbacks
def send_update_to_slaves(originating_ip, hosts):
    # FIXME: do this in a separate thread
    for slave in config.slaves:
        logging.debug("Sending update to slave {}".format(slave))
        print("slave: {}".format(slave))
        data = {
            "ip": originating_ip,
            "hosts": hosts
        }
        data_json = json.dumps(data)
        logging.debug("json data: {}".format(data_json))
        crypted = _slave_boxes[slave].encrypt(data_json)
        print("crypted: {}".format(crypted))
        base64 = crypted.encode('base64')
        print("base64 encoded crypted data: {}".format(base64))

        server = yield deferToThread(ServerProxy, slave)
        #yield deferToThread(server.peering_update, server, base64)
        slave_key = config.slaves[slave].encode('hex')
        server.peering_update(slave_key, base64)
        yield deferToThread(server.close, server)

@inlineCallbacks
def handle_update_from_slave(slave_key, update):
    slave = None
    for _slave in config.slaves:
        if config.slaves[_slave] == slave_key:
            slave = _slave
            break
    if slave is None:
        logger.warning("Got update from unknown slave with key {}".format(slave_key.encode('hex')))

@inlineCallbacks
def handle_update_from_master(master_key, update):
    if master_key != config.master["key"]:
        logging.error("I am a slave, got update from somewhere with unknown key {}".format(master_key.encode('hex')))
        raise Exception("Unknown key {}".format(master_key.encode('hex')))
    json = _master_box.decrypt(update)
    logger.info("Update from master as json: {}".format(json))

def load_keys():
    global _own_key
    global _master_box
    global _slave_boxes

    try:
        _own_key = libnacl.utils.load_key(config.key_file)
    except:
        _own_key = libnacl.public.SecretKey()
        _own_key.save(config.key_file)

    if config.is_master:
        _slave_boxes = {
            slave: 
            libnacl.public.Box(_own_key.sk, libnacl.public.PublicKey(config.slaves[slave]))
            for slave in config.slaves
        }
    else:
        if config.master is not None:
            master_key = libnacl.public.PublicKey(config.master["key"])
            #print("Using master key: {} -> {}".format(config.master["key"], master_key))
            _master_box = libnacl.public.Box(_own_key.sk, master_key)

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
