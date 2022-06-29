# README for denyhosts-server

`denyhosts-server` is a server that allows `denyhosts` clients to share blocked IP
addresses. It is intended to be a drop-in replacement for the service at
`xmlrpc.denyhosts.net` that up to now has been provided by the original author
of `denyhosts`.

## Features
- Drop-in replacement for legacy `denyhosts` sync server
- Supports sqlite and mysql databases
- Can run as non-privileged user
- Supports database evolution for easy upgrades
- Robust design which supports hundreds of connections per second
- Supports bootstrapping from legacy server
- Synchronisation algorithm that has safeguards against database poisoning
- Fully configurable
- Dynamically generated statistics web page
- Peering mode: multiple servers can shared their information for load-balancing
and to prevent a single point of failure
- `denyhosts-server` is developed and tested on a Debian GNU/Linux system. It should
  work on any Linux system with Python. Microsoft Windows is not a supported
  platform, although it should work without major modifications.

## Prerequisites
- MySQL database is preferred for large sites. For testing purposes sqlite is
  also supported
- Python 3 with setuptools (tested with Python 3.9). On an Ubuntu 21.04 system, run `apt install python-is-python3 python3-setuptools`
-  The GeoIP library needs the libgeoip development headers. On a Debian system,
  install them by running `apt-get install libgeoip-dev`. To install the
  free GeoIP database, run `apt-get install geoip-database`.
  Note: To install the Python GeoIP library on FreeBSD, edit your
  `~/.pydistutils.cfg` to contain the following:
  ```
  [build_ext]
  include_dirs=/usr/local/include
  library_dirs=/usr/local/lib
  ```
- The libnacl used to manage encryption key relies on libsodium. Make sure you install it. On a Ubuntu system, run `apt install libsodium23`.
- The other Python libraries will be installed automatically by the setup.py script.
- On most installations the sqlite3 Python library comes with Python 3.
- If you use a MySQL database, you need to install the appropriate Python
  library. possibly by running `pip install MySQL-python`. On Debian/Ubuntu,
  use `apt-get install python-mysqldb`.
- If you're on a Debian, and possible also Ubuntu system, you can install all pre-requisite like this: `apt install python-is-python3 python3-setuptools libgeoip-dev libsodium23 libpython3.9-dev`
  

## Installation
To do a global installation on your machine:
- After cloning the repo, go in the root dir of the repo and run the following command: `sudo setup.py install` to download the needed 
Python libraries. It will install all pre-req python libraries in you local dist-packages location (`/usr/local/lib/python3.9/dist-packages`)
as well as deploy `denyhosts-server` in you executable location (`/usr/local/bin`).

If you want to isolate in a virtual environment (make sure you have venv module installed: `apt install python3.9-venv`), run first `python -m venv .venv` and activate your environment (`source .venv/bin/activate`)


## Configuration
- Create the database and a database user with full rights to it.
- Copy the `denyhosts-server.conf.example` file to `/etc/denyhosts-server.conf` and edit it.
Fill in the database parameters, the location of the log file (which should be
writable by the system user that will be running denyhosts-server) and
other settings you wish to change. `graph_dir` in the `stats` sections is
another location that should be writable by `denyhosts-server`.
- If you haven change the default logging configuration, make sure `/var/log/denyhosts-server` is created and write accessible
from the user running `denyhosts-server`
- If you haven change the default logging configuration, make sure `/var/lib/denyhosts-server` is created and write accessible
from the user running `denyhosts-server`
- Prepare the database for first use with the command `denyhosts-server --recreate-database`. This will create the tables needed by denyhosts-server.

## Running denyhosts-server
Simply run `denyhosts-server`. Unless there are unexpected errors, this will give no
output and the server will just keep running. Configure your DenyHosts clients
to use the new synchronisation server by setting
```
SYNC_SERVER=http://your.host.name:9911
```
Once the server is running, you can watch the statistics page at
`http://your.host.name:9911`. 

These URLs look the same, but the xmlrpc library from the `DenyHosts`
client will actually connect to `http://your.host.name:9911/RPC2`. The port
numbers are configurable. The statistics page can be on the same port as
the RPC server, or on another.

The statistics page is updated by default every 10 minutes (configurable with
the `update_frequency` settings). The graphs on the statistics page will only
be generated when there is at least one report in the database.

## Signals
When `denyhosts-server` receives the `SIGHUP` signal, it will re-read the
configuration file. Changes to the database configuration are ignored.

## Updates
Installing the new version of `denyhosts-server` with `./setup.py install`.
Edit the configuration file at `/etc/denyhosts-server.conf` to configure any new
feature added since the last release. Check `changelog.txt` for new
configuration items.

Stop denyhosts-server, update the database tables by running `denyhosts-server --evolve-database` and
restart denyhosts-server.

## Maintenance
Old reports will be automatically purged by the configurable maintenance job.
See the configuration file for configuration options. To clean all reports by
clients, use the `--purge-reported-addresses` command line option. To clean all
reports retrieved from the legacy sync server, use the
`--purge-legacy-addresses` command line option. To purge a specific IP address
from both the reported and the legacy host lists, use the `--purge-ip` command
line option.

Note: Use these options with care. Do not use them while `denyhosts-server` is
running, since this may cause database inconsistencies. Use the `--force`
command line options to skip the safety prompt when using the purge options.

## Peering
If you wish to configure peering between multiple servers, do the following.
In the configuration file look at the `[peering]` section. Set the
`key_file` option and restart `denyhosts-server`. It will create a new key file
if it doesn't exist yet. If you look at the contents of the key file, note that
it contains two keys. The `pub` (for "public") key should be used in the 
configuration files of the peers.

For each peer, add two lines to the `[peering]` section. If you name the peer 
`PEERNAME`, add the peer's url as `peer_PEERNAME_url` and add its public key 
(a 32-byte random number, represented as a hexadecimal string) as 
`peer_PEERNAME_key`. 

Make sure that the peering configuration of all participating peers is consistent, 
i.e., every peer should know the URLs and keys of all other peers. You can use the
`--check-peers` command line option to perform this consistency check. It will 
ask all configured peers for their list of peers, and compare them with the ones
it knows.

All peer-to-peer communication is fully encrypted and authenticated, to prevent
denial of service attacks. Peers will share reports by clients directly when 
received. If a peer is offline for a while, it will NOT receive the reports
it missed.

When you add a new peer, you can bootstrap its database from one of the existing
peers using the `--bootstrap-from-peer`` option. Give the URL of the peer you
want to bootstrap from as parameter. The bootstrap option is not very well
optimized since it is not anticipated to be used very often.

## Links
- [`denyhosts-server` project site](https://github.com/janpascal/denyhosts_sync)
- [`denyhosts` project site](https://github.com/denyhosts/denyhosts)
- [Information on synchronisation algorithm](https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=622697)
- [Original, seemingly abandoned `DenyHosts` project](http://www.denyhosts.net)

## Copyright and license

### denyhosts-server
Copyright (C) 2015-2017 Jan-Pascal van Best <janpascal@vanbest.org>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

### Synchronisation algorithm
The synchronisation algorithm implemented in denyhosts-server is based
on an article by Anne Bezemer, published as Debian bug#622697 and
archived at [Debian bug#622697](https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=622697)
The article is Copyright (C) 2011 J.A. Bezemer <j.a.bezemer@opensourcepartners.nl>
and licensed "either GPL >=3 or AGPL >=3, at your option".
