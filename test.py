#!/usr/bin/env python
import xmlrpclib
import time

s = xmlrpclib.ServerProxy('http://localhost:8000/xmlrpc/')

print("Adding two hosts")
print s.add_hosts(["127.0.0.3", "test.example.org","test2.example.org"])
print("Adding one host")
print s.add_hosts(["test4.example.org"])

print("New crackers, resilience=3600") 
print s.get_new_hosts(time.time()-3600, 3, ["old.example.net"], 3600)
print("New crackers, resilience=60") 
print s.get_new_hosts(time.time()-3600, 3, ["old.example.net"], 60)
print("New crackers, resilience=60, min_reporters=2") 
print s.get_new_hosts(time.time()-3600, 2, ["old.example.net"], 60)
print("New crackers, resilience=60, min_reporters=1") 
print s.get_new_hosts(time.time()-3600, 1, ["old.example.net"], 60)
print("All hosts:")
print s.list_all_hosts()
# #print s.dump_database()
# 
print("Cracker info for test.example.org:")
print s.get_cracker_info("127.0.0.3")
# 
