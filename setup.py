#!/usr/bin/env python

from distutils.core import setup

from dh_syncserver import version

setup(name='dh_syncserver',
      version=version,
      description='DenyHosts Synchronisation Server',
      author='Jan-Pascal van Best',
      author_email='janpascal@vanbest.org',
      url='http://www.github.com/janpascal/denyhosts_sync_server',
      packages=['dh_syncserver'],
      requires=["twisted.enterprise.adbapi", "twistar"],
      scripts=['scripts/dh_syncserver'],
      license="AGPL",
     )
