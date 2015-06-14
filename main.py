from datetime import datetime
import sqlite3
import time

from twisted.web import xmlrpc, server
from twisted.web.xmlrpc import withRequest
from twisted.enterprise import adbapi

from models import Cracker, Report, get_cracker

class Example(xmlrpc.XMLRPC):
    """
    An example object to be published.
    """

    def __init__(self, dbpool):
        xmlrpc.XMLRPC.__init__(self)
        self.dbpool = dbpool

    def _add_hosts(self, txn, request, hosts):
        for host in hosts:
            print("Adding host {}".format(host))
            cracker = get_cracker(txn, host)
            cracker.add_report(txn, request.getClientIP())
            cracker.save(txn)

        return 42

    @withRequest
    def xmlrpc_add_hosts(self, request, hosts):
        print("add_hosts({})".format(hosts))
        return self.dbpool.runInteraction(self._add_hosts, request, hosts)

    @withRequest
    def xmlrpc_get_new_hosts(self, request, timestamp, threshold, hosts_added, resiliency):
        print("get_new_hosts({},{},{},{})".format(timestamp, threshold, hosts_added, resiliency))
        result = {}
        result['timestamp'] = time.time()
        result['hosts'] = ["badguy.example.net"]
        print("returning: {}".format(result))
        return result

#    def xmlrpc_list_all_hosts(self):
#        result = [cracker.ip_address for cracker in self.crackers]
#        return result

#    def xmlrpc_dump_database(self):
#        return self.crackers

    def _get_cracker_info(self, txn, ip_address):
        cracker = get_cracker(txn, ip_address)
        return cracker

    def xmlrpc_get_cracker_info(self, ip_address):
        return self.dbpool.runInteraction(self._get_cracker_info, ip_address)

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
    print("Creating tables")
    db = sqlite3.connect("denyhosts.sqlite")
    db.execute("DROP TABLE IF EXISTS crackers")
    db.execute("CREATE TABLE crackers (id INTEGER PRIMARY KEY AUTOINCREMENT, ip_address TEXT, first_time INTEGER, latest_time INTEGER, total_reports INTEGER)")
    db.execute("DROP INDEX IF EXISTS cracker_ip_address")
    db.execute("CREATE INDEX cracker_ip_address ON crackers (ip_address)")
    db.execute("DROP TABLE IF EXISTS reports")
    db.execute("CREATE TABLE reports(id INTEGER PRIMARY KEY AUTOINCREMENT, cracker_id INTEGER, ip_address TEXT, first_report_time INTEGER, latest_report_time INTEGER)")
    db.close()
    dbpool = adbapi.ConnectionPool("sqlite3", 'denyhosts.sqlite')
    from twisted.internet import reactor
    r = Example(dbpool)
    reactor.listenTCP(8000, server.Site(r))
    print("Starting reactor...")
    reactor.run()
    dbpool.close()

