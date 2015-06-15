#!/usr/bin/env python
import xmlrpclib
import time

s = xmlrpclib.ServerProxy('http://localhost:8000/xmlrpc/')
print s.add_hosts(["test.example.org","test2.example.org"])
print s.add_hosts(["test4.example.org"])

# print s.get_new_hosts(time.time()-3600, 3, ["old.example.net"], 3600)
# print s.get_new_hosts(time.time()-3600, 3, ["old.example.net"], 60)
print s.get_new_hosts(time.time()-3600, 2, ["old.example.net"], 60)
print s.get_new_hosts(time.time()-3600, 1, ["old.example.net"], 60)
print s.list_all_hosts()
# #print s.dump_database()
# 
print s.get_cracker_info("test.example.org")
# 
