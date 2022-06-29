#!/usr/bin/env python

from xmlrpc.client import ServerProxy
import time
import sys


server = 'http://localhost:9911'
print("Connecting to server {}".format(server))
s = ServerProxy(server)

#print(s.add_hosts(["127.0.0.3"]))
#print(s.add_hosts(["192.168.1.22"]))
print("Adding one host (four times)")
print(s.add_hosts(["69.192.72.154"]))
print(s.add_hosts(["69.192.72.155"]))
print(s.add_hosts(["69.192.72.156"]))
print(s.add_hosts(["69.192.72.157"]))

# Concurrency testing
#for i in range(0, 100):
#    print("Running test {}".format(i))
#    s.debug.test()
#    print("Running maintenance")
#    s.debug.maintenance()
#    time.sleep(5)

s.debug.test()
s.debug.maintenance()

#print s.add_hosts(["test4.example.org"])

#print("New crackers, resilience=3600") 
#print s.get_new_hosts(time.time()-3600, 3, ["old.example.net"], 3600)
#print("New crackers, resilience=60") 
#print s.get_new_hosts(time.time()-3600, 3, ["old.example.net"], 60)
#print("New crackers, resilience=60, min_reporters=2") 
#print s.get_new_hosts(time.time()-3600, 2, ["old.example.net"], 60)
#print("New crackers, resilience=60, min_reporters=1") 
#print s.get_new_hosts(time.time()-3600, 1, ["old.example.net"], 60)
print("Illegal arguments: ")
try:
    print(s.get_new_hosts("12312iasda", 1, ["old.example.net"], 60))
except Exception as e:
    print(e)
print("New crackers, resilience=60, min_reporters=1") 
print(s.get_new_hosts(time.time()-3600, 1, ["69.192.72.154"], 60))

peer1 = 'http://localhost:9921'
print("Connecting to server {}".format(peer1))
s1 = ServerProxy(peer1)

print("peer1 new crackers, resilience=60, min_reporters=1") 
print(s1.get_new_hosts(time.time()-3600, 1, ["69.192.72.154"], 60))

print("peer0 all hosts:")
print(s.debug.list_all_hosts())

print("peer1 all hosts:")
print(s1.debug.list_all_hosts())

print("peer1 add 1 host:")
print(s1.add_hosts(["69.192.72.158"]))

print("peer1 all hosts:")
print(s1.debug.list_all_hosts())

#print("All hosts:")
#print(s.list_all_hosts())
# #print(s.dump_database())
# 
#print("Cracker info for 69.192.72.154:")
#try:
#    print(s.get_cracker_info("69.192.72.154"))
#except Exception as e:
#    print e
# 
