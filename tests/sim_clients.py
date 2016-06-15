#!/usr/bin/env python
import xmlrpclib
import time
import threading
import random
import ipaddr

def is_valid_ip_address(ip_address):
    try:
        ip = ipaddr.IPAddress(ip_address)
    except:
        return False
    if (ip.is_reserved or ip.is_private or ip.is_loopback or
        ip.is_unspecified or ip.is_multicast or
        ip.is_link_local):
        return False
    return True

def random_ip_address():
    while True:
        ip = ".".join(map(str, (random.randint(0, 255) for _ in range(4))))
        if is_valid_ip_address(ip):
            return ip

server = 'http://localhost:9911'

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


run_sim(server, 60, 100)



