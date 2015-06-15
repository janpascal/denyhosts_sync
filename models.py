import time
from functools import partial
from twistar.dbobject import DBObject
from twisted.internet.defer import inlineCallbacks, returnValue
from twistar.registry import Registry

class Cracker(DBObject):
    HASMANY=['reports']

    @inlineCallbacks
    def add_report(self, client_ip):
        now = time.time()
        report = yield Report.find(
            where=["cracker_id=? AND ip_address=?", self.id, client_ip],
            limit=1
        )
        if report is None:
            report = Report(ip_address=client_ip, first_report_time=now, latest_report_time=now)
            yield report.save()
            self.current_reports += 1
            yield report.cracker.set(self)
        else:
            report.latest_report_time = now
            yield report.save()
        
        self.total_reports += 1
        self.latest_time = now

        returnValue(report)

    def resiliency(self):
        return self.latest_time - self.first_time

    def __str__(self):
        return "Cracker({},{},{},{},{},{})".format(self.id,self.ip_address,self.first_time,self.latest_time,self.total_reports,self.current_reports)

def get_cracker(ip_address):
    return Cracker.find(where=["ip_address=?",ip_address], limit=1)

class Report(DBObject):
    BELONGSTO=['cracker']

    @inlineCallbacks
    def latest_total_resiliency(self):
        # Fails
        cracker = yield self.cracker.get()
        returnValue(self.latest_report_time - cracker.first_report_time)

@inlineCallbacks
def get_qualifying_crackers(N, T, S1):
    # Initial version, see
    # https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=622697
    # for algorithm. 
    # Not complete yet!
    cracker_ids = yield Registry.DBPOOL.runQuery("""
            SELECT DISTINCT c.id, c.ip_address 
            FROM crackers c 
            JOIN reports r ON r.cracker_id=c.id
            WHERE (c.current_reports >= ?) AND 
                (c.latest_time - c.first_time >= ?)
                AND (c.latest_time >= ?)
            ORDER BY c.first_time DESC
            LIMIT ?
        """, 
        [N, T, S1, 50])
    
    print("Cracker ids:{}".format(cracker_ids))
    if cracker_ids is None:
        returnValue( [])
    else:
        returnValue([r[1] for r in cracker_ids])

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4

