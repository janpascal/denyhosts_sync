#!/usr/bin/env python

from setuptools import setup
from glob import glob
from denyhosts_server import version

etcpath = "/etc"

setup(name='denyhosts-server',
      version=version,
      description='DenyHosts Synchronisation Server',
      author='Jan-Pascal van Best',
      author_email='janpascal@vanbest.org',
      url='https://github.com/janpascal/denyhosts_sync',
      packages=['denyhosts_server'],
      install_requires=["Twisted", "twistar", "ipaddr", "jinja2", "numpy", "matplotlib", "GeoIP", "minify", "libnacl"],
      scripts=['scripts/denyhosts-server'],
      data_files=[
        ('static/js', glob('static/js/*.min.js')),
        ('static/css', glob('static/css/*.min.css')),
        ('static/graph', glob('static/graph/README')),
        ('template', glob('template/*')),
        ('docs', [
                    'README.md', 
                    'LICENSE.md', 
                    'changelog.txt', 
                    'denyhosts-server.conf.example',
                    'denyhosts-server.service.example', 
                    'denyhosts-server.init.example' 
                ]
        ),
      ],
      license="""
Copyright (C) 2015-2020 Jan-Pascal van Best <janpascal@vanbest.org>

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
