import asyncio
import time

from denyhosts_server import models
from denyhosts_server import controllers 
from denyhosts_server import views 
from denyhosts_server.models import Cracker, Report

def random_ip_address():
    return ".".join(map(str, (random.randint(0, 255) for _ in range(4))))

class MockRequest:
    def __init__(self, ip):
        self.remote = ip
        self.headers = {}

    def getClientIP(self):
        return self._ip

    
async def test_try_and_confuse_server():
    request = MockRequest("127.0.0.1")
    view = views.AppView(request)
    for i in range(0, 25):
        print("count:{}".format(i))

        tasks = []
        for t in range(5):
            tasks.append(asyncio.create_task(view.rpc_add_hosts(["1.1.1.1", "2.2.2.2"])))
        for t in range(5):
            tasks.append(asyncio.create_task(view.rpc_add_hosts(["1.1.1.7", "2.2.2.8"])))
        tasks.append(controllers.perform_maintenance())
        
        await asyncio.gather(*tasks)

""""
    def run(self, count):
        for i in xrange(count):
            ip = random_ip_address()
            try:
                self.view.add_hosts([ip])
                self.view.get_new_hosts(time.time()-480, 3, [ip], 3600)
            except Exception, e:
                print("Got exception {}".format(e))

    
    def test_simulate_clients(self):
        num_threads = 20
        num_runs = 100
        threads = []

        print("Creating threads...")
        for i in xrange(num_threads):
            thread = threading.Thread(target=run, args=(num_runs))
            threads.append(thread)

        print("Starting threads...")
        for i in xrange(num_threads):
            threads[i].start()

        #print("Waiting for threads...")
        for i in xrange(num_threads):
            threads[i].join()
"""
