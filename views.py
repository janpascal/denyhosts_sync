import time
from functools import partial

from twisted.web import xmlrpc 
from twisted.web.xmlrpc import withRequest
from twisted.internet.defer import inlineCallbacks, returnValue

import models
from models import Cracker, Report

class Server(xmlrpc.XMLRPC):
    """
    An example object to be published.
    """

    def __init__(self):
        xmlrpc.XMLRPC.__init__(self)

    @withRequest
    @inlineCallbacks
    def xmlrpc_add_hosts(self, request, hosts):
        print("add_hosts({})".format(hosts))
        for cracker_ip in hosts:
            print("Adding host {}".format(cracker_ip))
            cracker = yield Cracker.find(where=['ip_address=?', cracker_ip], limit=1)
            if cracker is None:
                now = time.time()
                cracker = Cracker(ip_address=cracker_ip, first_time=now, latest_time=now, total_reports=0, current_reports=0)
                yield cracker.save()
            yield cracker.add_report(request.getClientIP())
            yield cracker.save()
        returnValue(0)

    @withRequest
    @inlineCallbacks
    def xmlrpc_get_new_hosts(self, request, timestamp, threshold, hosts_added, resiliency):
        print("get_new_hosts({},{},{},{})".format(timestamp, threshold, hosts_added, resiliency))
        #return self.dbpool.runInteraction(self._get_new_hosts, request, timestamp, threshold, hosts_added, resiliency)
        result = {}
        result['timestamp'] = time.time()
        result['hosts'] = yield models.get_qualifying_crackers(threshold, resiliency, timestamp)
        print("returning: {}".format(result))
        returnValue( result)

    @inlineCallbacks
    def xmlrpc_list_all_hosts(self):
        crackers = yield Cracker.all()
        returnValue([c.ip_address for c in crackers])

#    def xmlrpc_dump_database(self):
#        return self.crackers

    @inlineCallbacks
    def xmlrpc_get_cracker_info(self, ip_address):
        print("Getting info for cracker {}".format(ip_address))
        cracker = yield models.get_cracker(ip_address)
        print("found cracker: {}".format(cracker))
        reports = yield cracker.reports.get()
        print("found reports: {}".format(reports))
        cracker_cols=['ip_address','first_time', 'latest_time', 'total_reports',
        'current_reports']
        report_cols=['ip_address','first_report_time', 'latest_report_time']
        returnValue( [cracker.toHash(cracker_cols), [r.toHash(report_cols) for r in reports]] )


    def xmlrpc_fault(self):
        """
        Raise a Fault indicating that the procedure should not be used.
        """
        raise xmlrpc.Fault(123, "The fault procedure is faulty.")

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
