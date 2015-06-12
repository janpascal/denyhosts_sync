from twisted.web import xmlrpc, server
from twisted.web.xmlrpc import withRequest
from models import Cracker, Report
from datetime import datetime
import time

class Example(xmlrpc.XMLRPC):
    """
    An example object to be published.
    """
    crackers=[]

    @withRequest
    def xmlrpc_add_hosts(self, request, hosts):
        print("add_hosts({})".format(hosts))
        for host in hosts:
            print("Adding host {}".format(host))
            candidates = [cracker for cracker in self.crackers if
                cracker.ip_address == host]
            if len(candidates)>1:
                print("Error, {} crackers for host {}!".format(len(candidates), host))
            elif len(candidates)==1:
                cracker = candidates[0]
            else:
                cracker = Cracker(host)
                self.crackers.append(cracker)
            cracker.add_report(request.getClientIP())

        return 0

    @withRequest
    def xmlrpc_get_new_hosts(self, request, timestamp, threshold, hosts_added, resiliency):
        print("get_new_hosts({},{},{},{})".format(timestamp, threshold, hosts_added, resiliency))
        result = {}
        result['timestamp'] = time.time()
        result['hosts'] = ["badguy.example.net"]
        print("returning: {}".format(result))
        return result

    def xmlrpc_list_all_hosts(self):
        result = [cracker.ip_address for cracker in self.crackers]
        return result

    def xmlrpc_dump_database(self):
        return self.crackers

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
    from twisted.internet import reactor
    r = Example()
    reactor.listenTCP(8000, server.Site(r))
    reactor.run()
