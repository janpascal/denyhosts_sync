#!/usr/bin/env python
import xmlrpclib
import time
import sys


server = 'http://localhost:9911'
print("Connecting to server {}".format(server))
s = xmlrpclib.ServerProxy(server)

peer1 = 'http://localhost:9921'
print("Connecting to server {}".format(peer1))
s1 = xmlrpclib.ServerProxy(peer1)

print("peer0 all hosts:")
print s.debug.list_all_hosts()

print("peer1 all hosts:")
print s1.debug.list_all_hosts()

print("peer0 cracker info for 69.192.72.154:")
try:
    print s.debug.get_cracker_info("69.192.72.154")
except Exception, e:
    print e
 
print("peer1 cracker info for 69.192.72.154:")
try:
    print s1.debug.get_cracker_info("69.192.72.154")
except Exception, e:
    print e
 
