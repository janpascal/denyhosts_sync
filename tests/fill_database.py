#!/usr/bin/env python3
from xmlrpc.client import ServerProxy, Fault
import time
import threading
import random

server = 'http://localhost:9911'
debug_server = 'http://localhost:9912'

def run(count, known_crackers):
    #print("Connecting to server {}".format(server))
    start_time = time.time()
    s_debug = ServerProxy(debug_server)
    s_debug.test_bulk_insert(count, known_crackers, start_time - random.random()*7*24*3600)
    #print("Inserting {} hosts took {} seconds".format(count, time.time() - start_time))

def run_insert_test(num_threads, count, known_crackers):
    start_time = time.time()

    threads = []
    #print("Creating threads...")
    for i in range(num_threads):
        thread = threading.Thread(target=run, args=(count, known_crackers))
        threads.append(thread)

    #print("Starting threads...")
    for i in range(num_threads):
        threads[i].start()

    #print("Waiting for threads...")
    for i in range(num_threads):
        threads[i].join()

    print("Inserting {} hosts {} times took {} seconds".format(count, num_threads, time.time() - start_time))
    print("Average time per insert: {} seconds".format( (time.time() - start_time) / count / num_threads))


s = ServerProxy(server)
s_debug = ServerProxy(debug_server)

for num_threads in range(20, 59):
    print("Inserting {} hosts {} times, please wait...".format(100, num_threads))
    s_debug.clear_bulk_cracker_list()
    run_insert_test(num_threads, 100, True)
    time.sleep(3)

    print("==============================================")

#s = ServerProxy(server)
#for i in range(100):
#    s.clear_bulk_cracker_list()
#    print("Adding 20*5000=100,000 hosts...")
#    run_insert_test(server, 20, 5000, False)



