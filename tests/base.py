import logging
import inspect
import os
import os.path

from dh_syncserver import config
from dh_syncserver import models
from dh_syncserver import main
from dh_syncserver import database

from twisted.trial import unittest
from twisted.enterprise import adbapi
from twisted.internet.defer import inlineCallbacks, returnValue

from twistar.registry import Registry

class TestBase(unittest.TestCase):
    @inlineCallbacks
    def setUp(self):
        configfile = os.path.join(
            os.path.dirname(inspect.getsourcefile(TestBase)),
            "test.conf"
        )

        config.read_config(configfile)

        Registry.DBPOOL = adbapi.ConnectionPool(config.dbtype, **config.dbparams)
        Registry.register(models.Cracker, models.Report, models.Legacy)

        yield database.clean_database()
        main.configure_logging()
