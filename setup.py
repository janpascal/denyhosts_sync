#!/usr/bin/env python

from setuptools import setup
from glob import glob
from dh_syncserver import version

etcpath = "/etc"

setup(name='dh_syncserver',
      version=version,
      description='DenyHosts Synchronisation Server',
      author='Jan-Pascal van Best',
      author_email='janpascal@vanbest.org',
      url='http://www.github.com/janpascal/denyhosts_sync_server',
      packages=['dh_syncserver'],
      install_requires=["Twisted", "twistar", "ipaddr", "jinja2", "pygal", "GeoIP"],
      scripts=['scripts/dh_syncserver'],
      data_files=[
        (etcpath, glob("dh_syncserver.conf")),
      ],
      license="""
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
"""
     )
