import time

from twisted.web import xmlrpc 
from twisted.web.xmlrpc import withRequest

import models
from models import Cracker, Report

class Server(xmlrpc.XMLRPC):
    """
    An example object to be published.
    """

    def __init__(self, dbpool):
        xmlrpc.XMLRPC.__init__(self)
        self.dbpool = dbpool

    def _add_hosts(self, txn, request, hosts):
        for host in hosts:
            print("Adding host {}".format(host))
            cracker = models.get_cracker(txn, host)
            cracker.add_report(txn, request.getClientIP())
            cracker.save(txn)

        return 42

    @withRequest
    def xmlrpc_add_hosts(self, request, hosts):
        print("add_hosts({})".format(hosts))
        return self.dbpool.runInteraction(self._add_hosts, request, hosts)

    def _get_new_hosts(self, txn, request, timestamp, threshold, hosts_added, resiliency):
        result = {}
        result['timestamp'] = time.time()
        result['hosts'] = models.get_qualifying_crackers(txn, threshold, resiliency, timestamp)
        print("returning: {}".format(result))
        return result

    @withRequest
    def xmlrpc_get_new_hosts(self, request, timestamp, threshold, hosts_added, resiliency):
        print("get_new_hosts({},{},{},{})".format(timestamp, threshold, hosts_added, resiliency))
        return self.dbpool.runInteraction(self._get_new_hosts, request, timestamp, threshold, hosts_added, resiliency)

    def _list_all_hosts(self, txn):
        crackers = models.get_all_crackers(txn)
        return [c.ip_address for c in crackers]

    def xmlrpc_list_all_hosts(self):
        return self.dbpool.runInteraction(self._list_all_hosts)

#    def xmlrpc_dump_database(self):
#        return self.crackers

    def _get_cracker_info(self, txn, ip_address):
        cracker = models.get_cracker(txn, ip_address)
        reports = models.get_all_reports_for_cracker(txn, cracker.id)
        return (cracker, reports)

    def xmlrpc_get_cracker_info(self, ip_address):
        return self.dbpool.runInteraction(self._get_cracker_info, ip_address)

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

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
