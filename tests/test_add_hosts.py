import time
import random

from xmlrpc.client import ServerProxy

from denyhosts_server import models
from denyhosts_server import controllers 
from denyhosts_server import views 
from denyhosts_server.models import Cracker, Report

from twisted.internet import reactor,defer,task
from twisted.internet.defer import inlineCallbacks, returnValue

from . import base

def random_ip_address():
    return ".".join(map(str, (random.randint(0, 255) for _ in range(4))))

def sleep(seconds):
    d = defer.Deferred()
    reactor.callLater(seconds, d.callback, seconds)
    return d

class MockHeaders:
    def __init__(self, ip):
        self._ip = ip

    def getRawHeaders(self,key):
        return [self._ip,]

class MockRequest:
    def __init__(self, ip):
        self._ip = ip
        self.received_headers = {}
        self.requestHeaders = MockHeaders(ip)

    def getClientIP(self):
        return self._ip

class AddHostsTest(base.TestBase):

    @inlineCallbacks
    def test_add_hosts_ByIP(self):
        self.view = views.Server()
        request = MockRequest("11.12.44.75")

        self.count = 0
        def called(result):
            self.count += 1

        def calledError(result):
            print("Error")
            self.count += 1

        ip_list = ['1.1.1.1', '1.2.3.4']

        task.deferLater(reactor, 0.01, self.view.xmlrpc_add_hosts, request,ip_list).addCallback(called).addErrback(calledError)
        self.count -= 1
            
        while self.count < 0:
            yield sleep(0.1)

        yield sleep(60)

        task.deferLater(reactor, 0.01, self.view.xmlrpc_add_hosts, request,ip_list).addCallback(called).addErrback(calledError)
        self.count -= 1
            
        while self.count < 0:
            yield sleep(0.1)

        hosts = yield controllers.get_qualifying_crackers(1, 0, 0, 50, [])
        self.assertEqual(hosts, ['1.2.3.4', '1.1.1.1'], "Wrong number of Crackers in database")

    @inlineCallbacks
    def test_add_hosts_ByName(self):
        self.view = views.Server()
        request = MockRequest("11.12.44.75")

        self.count = 0
        def called(result):
            self.count += 1

        def calledError(result):
            print("Error")
            self.count += 1

        ip_list = ['ec2-161-189-70-219.cn-northwest-1.compute.amazonaws.com.cn', 'static.28.30.55.162.clients.your-server.de']

        task.deferLater(reactor, 0.01, self.view.xmlrpc_add_hosts, request,ip_list).addCallback(called).addErrback(calledError)
        self.count -= 1
            
        while self.count < 0:
            yield sleep(0.1)
        
        hosts = yield controllers.get_qualifying_crackers(1, 0, 0, 50, [])
        self.assertEqual(hosts, ['162.55.30.28', '161.189.70.219'], "Wrong number of Crackers in database")

    @inlineCallbacks
    def test_add_hosts_Mix(self):
        self.view = views.Server()
        request = MockRequest("11.12.44.75")

        self.count = 0
        def called(result):
            self.count += 1

        def calledError(result):
            print("Error")
            self.count += 1

        ip_list = ['134.65.845.98', 'tor-exit-relay-2.anonymizing-proxy.digitalcourage.de', '6.89.34.25', 'hsi-kbw-078-042-091-125.hsi3.kabel-badenwuerttemberg.de']

        task.deferLater(reactor, 0.01, self.view.xmlrpc_add_hosts, request,ip_list).addCallback(called).addErrback(calledError)
        self.count -= 1
            
        while self.count < 0:
            yield sleep(0.1)
        
        hosts = yield controllers.get_qualifying_crackers(1, 0, 0, 50, [])
        self.assertEqual(hosts, ['185.220.102.248', '78.42.91.125', '6.89.34.25', ], "Wrong number of Crackers in database")
    
    @inlineCallbacks
    def test_add_hosts_ByName_With_Dupe(self):
        self.view = views.Server()
        request = MockRequest("11.12.44.75")

        self.count = 0
        def called(result):
            self.count += 1

        def calledError(result):
            print("Error")
            self.count += 1

        ip_list = ['ec2-161-189-70-219.cn-northwest-1.compute.amazonaws.com.cn', 'static.28.30.55.162.clients.your-server.de', 'ec2-161-189-70-219.cn-northwest-1.compute.amazonaws.com.cn']

        task.deferLater(reactor, 0.01, self.view.xmlrpc_add_hosts, request,ip_list).addCallback(called).addErrback(calledError)
        self.count -= 1
            
        while self.count < 0:
            yield sleep(0.1)
        
        hosts = yield controllers.get_qualifying_crackers(1, 0, 0, 50, [])
        self.assertEqual(hosts, ['162.55.30.28', '161.189.70.219'], "Wrong number of Crackers in database")