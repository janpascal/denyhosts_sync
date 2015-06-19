#    denyhosts sync server
#    Copyright (C) 2015 Jan-Pascal van Best <janpascal@vanbest.org>

#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.

#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

import time

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

    def __str__(self):
        return "Report({},{},{},{})".format(self.id,self.ip_address,self.first_report_time,self.latest_report_time)

    @inlineCallbacks
    def latest_total_resiliency(self):
        # Fails
        cracker = yield self.cracker.get()
        returnValue(self.latest_report_time - cracker.first_report_time)

@inlineCallbacks
def get_qualifying_crackers(min_reports, min_resilience, previous_timestamp, max_crackers=50):
    # Thank to Anne Bezemer for the algorithm in this function. 
    # See https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=622697
    
    # This query takes care of conditions (a) and (b)
    cracker_ids = yield Registry.DBPOOL.runQuery("""
            SELECT DISTINCT c.id, c.ip_address 
            FROM crackers c 
            JOIN reports r ON r.cracker_id=c.id
            WHERE (c.current_reports >= ?) AND 
                (c.latest_time - c.first_time >= ?)
                AND (c.latest_time >= ?)
            ORDER BY c.first_time DESC
        """, 
        [min_reports, min_resilience, previous_timestamp])
  
    if cracker_ids is None:
        returnValue([])

    result = []
    for c in cracker_ids:
        cracker_id = c[0]
        cracker = yield Cracker.find(cracker_id)
        print("Examining cracker:")
        print(cracker)
        reports = yield cracker.reports.get(orderby="first_report_time ASC")
        print("reports:")
        for r in reports:
            print("    "+str(r))
        if (len(reports)>=min_reports and 
            reports[min_reports-1].first_report_time >= previous_timestamp): 
            # condition (c) satisfied
            print("c")
            result.append(cracker.ip_address)
        else:
            print("checking (d)...")
            satisfied = False
            for report in reports:
                print("    "+str(report))
                if (not satisfied and 
                    report.latest_report_time>=previous_timestamp and
                    report.latest_report_time-cracker.first_time>=min_resilience):
                    print("    d1")
                    satisfied = True
                if (report.latest_report_time<=previous_timestamp and 
                    report.latest_report_time-cracker.first_time>=min_resilience):
                    print("    d2 failed")
                    satisfied = False
                    break
            if satisfied:
                print("Appending {}".format(cracker.ip_address))
                result.append(cracker.ip_address)
            else:
                print("    skipping")
        if len(result)>=max_crackers:
            break

    returnValue(result)

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
