#!/usr/bin/env python
import xmlrpclib
import time
import threading
import random

server = 'http://localhost:9911'

def run(server, count, known_crackers):
    #print("Connecting to server {}".format(server))
    s = xmlrpclib.ServerProxy(server)
    start_time = time.time()
    s.debug.test_bulk_insert(count, known_crackers, start_time - random.random()*7*24*3600)
    #print("Inserting {} hosts took {} seconds".format(count, time.time() - start_time))

def run_insert_test(server, num_threads, count, known_crackers):
    start_time = time.time()

    threads = []
    #print("Creating threads...")
    for i in xrange(num_threads):
        thread = threading.Thread(target=run, args=(server, count, known_crackers))
        threads.append(thread)

    #print("Starting threads...")
    for i in xrange(num_threads):
        threads[i].start()

    #print("Waiting for threads...")
    for i in xrange(num_threads):
        threads[i].join()

    print("Inserting {} hosts {} times took {} seconds".format(count, num_threads, time.time() - start_time))
    print("Average time per insert: {} seconds".format( (time.time() - start_time) / count / num_threads))


s = xmlrpclib.ServerProxy(server)
for num_threads in xrange(20, 59):
    print("Inserting {} hosts {} times, please wait...".format(100, num_threads))
    s.debug.clear_bulk_cracker_list()
    run_insert_test(server, num_threads, 100, True)
    time.sleep(3)

    print("==============================================")

#s = xmlrpclib.ServerProxy(server)
#for i in xrange(100):
#    s.clear_bulk_cracker_list()
#    print("Adding 20*5000=100,000 hosts...")
#    run_insert_test(server, 20, 5000, False)



