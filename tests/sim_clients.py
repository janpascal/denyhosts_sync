#!/usr/bin/env python
import xmlrpclib
import time
import threading
import random

def random_ip_address():
    return ".".join(map(str, (random.randint(0, 255) for _ in range(4))))

server = 'http://localhost:9911/xmlrpc/'

def run(server, count):
    # Assuming every client will supply 1 new host every 8minutes
    # and ask for newly recognised crackers
    s = xmlrpclib.ServerProxy(server)
    for i in xrange(count):
        ip = random_ip_address()
        try:
            s.add_hosts([ip])
            s.get_new_hosts(time.time()-480, 3, [ip], 3600)
        except Exception, e:
            print("Got exception {}".format(e))

def run_sim(server, num_threads, count):
    start_time = time.time()

    threads = []
    print("Creating threads...")
    for i in xrange(num_threads):
        thread = threading.Thread(target=run, args=(server, count))
        threads.append(thread)

    print("Starting threads...")
    for i in xrange(num_threads):
        threads[i].start()

    #print("Waiting for threads...")
    for i in xrange(num_threads):
        threads[i].join()

    end_time = time.time()
    print("Simulation {} clients {} times took {} seconds".format(count, num_threads, end_time - start_time))
    print("Average time per client : {} seconds".format( (end_time - start_time) / count / num_threads))
    print("Average requests per seconds: {}".format( 
        count * num_threads / (end_time - start_time)))


run_sim(server, 30, 100)



