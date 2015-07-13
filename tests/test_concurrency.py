import time

from dh_syncserver import models
from dh_syncserver import controllers 
from dh_syncserver import views 
from dh_syncserver.models import Cracker, Report

from twisted.internet import reactor,defer,task
from twisted.internet.defer import inlineCallbacks, returnValue

import base

def random_ip_address():
    return ".".join(map(str, (random.randint(0, 255) for _ in range(4))))

def sleep(seconds):
    d = defer.Deferred()
    reactor.callLater(seconds, d.callback, seconds)
    return d

class MockRequest:
    def __init__(self, ip):
        self._ip = ip

    def getClientIP(self):
        return self._ip

class ConcurrencyTest(base.TestBase):

    @inlineCallbacks
    def test_try_and_confuse_server(self):
        self.view = views.Server()
        request = MockRequest("127.0.0.1")
        for i in range(0, 50):
            print("count:{}".format(i))

            self.count = 0
            def called(result):
                self.count += 1
           
            for t in range(5):
                task.deferLater(reactor, 0.01, self.view.xmlrpc_add_hosts, request, ["1.1.1.1", "2.2.2.2"]).addCallback(called)
                self.count -= 1
            for t in range(5):
                task.deferLater(reactor, 0.01, self.view.xmlrpc_add_hosts, request, ["1.1.1.7", "2.2.2.8"]).addCallback(called)
                self.count -= 1
            task.deferLater(reactor, 0.01, controllers.perform_maintenance).addCallback(called)
            self.count -= 1
            
            while self.count < 0:
                yield sleep(0.1)
""""
    def run(self, count):
        for i in xrange(count):
            ip = random_ip_address()
            try:
                self.view.add_hosts([ip])
                self.view.get_new_hosts(time.time()-480, 3, [ip], 3600)
            except Exception, e:
                print("Got exception {}".format(e))

    @inlineCallbacks
    def test_simulate_clients(self):
        num_threads = 20
        num_runs = 100
        threads = []

        print("Creating threads...")
        for i in xrange(num_threads):
            thread = threading.Thread(target=run, args=(num_runs))
            threads.append(thread)

        print("Starting threads...")
        for i in xrange(num_threads):
            threads[i].start()

        #print("Waiting for threads...")
        for i in xrange(num_threads):
            threads[i].join()
"""
