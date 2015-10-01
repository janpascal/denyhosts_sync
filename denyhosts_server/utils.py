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

import logging

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet import reactor, task

_hosts_busy = set()

@inlineCallbacks
def wait_and_lock_host(host):
    try:
        while host in _hosts_busy:
            logging.debug("waiting to update host {}, {} blocked now".format(host, len(_hosts_busy)))
            yield task.deferLater(reactor, 0.01, lambda _:0, 0)
        _hosts_busy.add(host)
    except:
        logging.debug("Exception in locking {}".format(host), exc_info=True)

    returnValue(0)

def unlock_host(host):
    try:
        _hosts_busy.remove(host)
        #logging.debug("host {} unlocked, {} blocked now".format(host, len(_hosts_busy)))
    except:
        logging.debug("Exception in unlocking {}".format(host), exc_info=True)

def none_waiting():
    return len(_hosts_busy) == 0

def count_waiting():
    return len(_hosts_busy)

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
