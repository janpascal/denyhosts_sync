# README for dh_syncserver

`dh_syncserver` is a server that allows `denyhosts` clients to share blocked IP
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

## Prerequisites
- MySQL database is preferred for large site. For testing purposes sqlite is
  also supported
- Python with setuptools
- The twisted framework and the twistar ORM library are installed automatically
  by the setup.py script
- dh_syncserver is developed and tested on a Debian GNU/Linux system. It should
  work on any Linux system with Python. Microsoft Windows is not a supported 
  platform, although it should work without major modifications.

## Installation
Run the following command: `sudo ./setup.py install`. This will download the
neede Python libraries, install the Python scripts onto your system (usually in
`/usr/local/lib/python2.7/dist-packages`), install the default configuration
file in `/etc/dh_syncserver.conf` and the Python script
`/usr/local/bin/dh_syncserver`.

## Configuration
Create the database and a database user with full rights to it.  Edit the 
configuration file in `/etc/dh_syncserver.conf`. Fill in the database
parameters, the location of the log file (which should be writable by the system
user that will be running dh_syncserver) and other settings you wish to change.

Prepare the database for first use with the command `dh_syncserver
--recreate-database`. This will create the tabled needed by dh_syncserver.

## Running dh_syncserver
Simple run `dh_syncserver`. Unless there are unexpected error, this will give no
output and the server will just keep running. 

## Updates
Installing the new version of `dh_syncserver` with `./setup.py install_scripts
install_lib`. Do not install the data parts of the package because it may
overwrite your configuration file.

Stop dh_syncserver, update the database tables by running `dh_syncserver --evolve-database` and
restart dh_syncserver.

## Links
- [`dh_syncserver` project site](https://github.com/janpascal/denyhosts_sync)
- [`denyhosts` project site](https://github.com/denyhosts/denyhosts)
- [Information on synchronisation algorithm](https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=622697)
- [Original, seemingly abandoned `DenyHosts` project](http://www.denyhosts.net)

## Copyright and license
Copyright (C) 2015 Jan-Pascal van Best <janpascal@vanbest.org>

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

