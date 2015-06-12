from twisted.web import xmlrpc, server
from twisted.web.xmlrpc import withRequest
from models import Cracker, Report
from datetime import datetime
import time
from storm.twisted.transact import Transactor
from storm.twisted.transact import transact
from twisted.python.threadpool import (ThreadPool)

class Example(xmlrpc.XMLRPC):
    """
    An example object to be published.
    """
    crackers=[]

    @withRequest
    @transact
    def xmlrpc_add_hosts(self, request, hosts):
        print("add_hosts({})".format(hosts))
        for host in hosts:
            print("Adding host {}".format(host))
            try:

                cracker = root.crackers[host]
            except:
                cracker = Cracker(host)
            cracker.add_report(host)
            self.crackers.append(cracker)

            try:
                report = root.reports[request.getClientIP()]
            except:
                report = Report(request.getClientIP())
            
            #report.latest_report_time = datetime.now()
            #report.latest_total_resiliency = report.latest_report_time - report.first_report_time
            #report.save()
        return 0

    @withRequest
    def xmlrpc_get_new_hosts(self, request, timestamp, threshold, hosts_added, resiliency):
        print("get_new_hosts({},{},{},{})".format(timestamp, threshold, hosts_added, resiliency))
        result = {}
        result['timestamp'] = time.time()
        result['hosts'] = ["badguy.example.net"]
        print("returning: {}".format(result))
        return result

    @withRequest
    def xmlrpc_list_all_hosts(self, request):
        result = [cracker.ip_address for cracker in self.crackers]
        return result

    @withRequest
    def xmlrpc_ip(self, request):
        """ 
        Return client ip address/
        """
        return request.getClientIP()

    def xmlrpc_echo(self, x):
        """
        Return all passed args.
        """
        return x

    def xmlrpc_add(self, a, b):
        """
        Return sum of arguments.
        """
        return a + b

    def xmlrpc_fault(self):
        """
        Raise a Fault indicating that the procedure should not be used.
        """
        raise xmlrpc.Fault(123, "The fault procedure is faulty.")

if __name__ == '__main__':
    threads = ThreadPool(maxthreads=4)
    transaction = Transactor(threads)

    from twisted.internet import reactor
    r = Example()
    reactor.listenTCP(8000, server.Site(r))
    reactor.run()
