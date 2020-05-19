#!/usr/bin/env python3
from xmlrpc.client import ServerProxy, Fault
import time
import sys


server = 'http://localhost:9911'

print(f"Connecting to server {server}")
s = ServerProxy(server)

for illegal_ip in ["127.0.0.3", "192.168.1.22", "test4.example.org"]:
    try:
        print(s.add_hosts([illegal_ip]))
    except Fault as e:
        if e.faultCode == 104:
            print(f"Successfully received Fault 104 when trying to add illegal IP address {illegal_ip}")
        else:
            raise e

print("Adding one host (four times)")
s.add_hosts(["69.192.72.154"])
s.add_hosts(["69.192.72.155"])
s.add_hosts(["69.192.72.156"])
s.add_hosts(["69.192.72.157"])

#print("Concurrency testing...")
#for i in range(0, 100):
#    print("Running test {}".format(i))
#    s.debug_test()
#    print("Running maintenance")
#    s.debug_maintenance()
#    #time.sleep(0.01)

s.debug_test()
s.debug_maintenance()

try:
    print(s.get_new_hosts("12312iasda", 1, ["69.192.72.150"], 60))
except Fault as e:
    if e.faultCode == 102:
        print(f"Successfully received Fault 102 when trying to get new hosts with illegal timestamp")
    else:
        raise e

print("New crackers, resilience=3600") 
print(s.get_new_hosts(time.time()-3600, 3, ["69.192.72.150"], 3600))
print("New crackers, resilience=60") 
print(s.get_new_hosts(time.time()-3600, 3, ["69.192.72.150"], 60))
print("New crackers, resilience=60, min_reporters=2") 
print(s.get_new_hosts(time.time()-3600, 2, ["69.192.72.150"], 60))
print("New crackers, resilience=60, min_reporters=1") 
print(s.get_new_hosts(time.time()-3600, 1, ["69.192.72.150"], 60))
print("New crackers, resilience=60, min_reporters=1") 
print(s.get_new_hosts(time.time()-3600, 1, ["69.192.72.154"], 60))

# Add a host and check that it is returned as a cracker
host = "69.192.72.159"
s.debug_clear_ip(host)
s.add_hosts([host])
time.sleep(5)
s.add_hosts([host])
hosts = s.get_new_hosts(time.time()-3600, 1, [], 1)["hosts"]
if host in hosts:
    print(f"Successfully registered {host} as a cracker!")
else:
    raise Exception(f"Failed to register {host} as a cracker")

if False:
    # Peering tests
    peer1 = 'http://localhost:9921'
    print("Connecting to server {}".format(peer1))
    s1 = ServerProxy(peer1)

    print("peer1 new crackers, resilience=60, min_reporters=1") 
    print(s1.get_new_hosts(time.time()-3600, 1, ["69.192.72.154"], 60))

    print("peer0 all hosts:")
    print(s.debug_list_all_hosts())

    print("peer1 all hosts:")
    print(s1.debug.list_all_hosts())

print("All hosts:")
print(s.debug_list_all_hosts())

# #print s.dump_database()
# 
print("Cracker info for 69.192.72.154:")
try:
    print(s.debug_get_cracker_info("69.192.72.154"))
except Exception as e:
    print(f"Exception while getting all info for cracker: {e}")
 
