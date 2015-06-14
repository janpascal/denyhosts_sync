from datetime import datetime
import time

class Cracker():
    def __init__(self, ip_address):
        self.ip_address = ip_address
        self.first_time = datetime.now()
        self.latest_time = self.first_time
        self.total_reports = 0
        #self.reports = []

    def add_report(self, txn, ip_address):
        self.latest_time = datetime.now()
        self.total_reports += 1
        report = get_report_for_cracker(txn, self, ip_address)
        report.latest_report_time = datetime.now();
        report.save(txn)

    def resiliency(self):
        return self.latest_time - self.first_time

    #def current_reports(self):
    #    return len(self.reports)

    #def find_report(self, ip_address):
    #    candidates = [report for report in self.reports if
    #        report.ip_address == ip_address]
    #    if len(candidates)>1:
    #        print("Error, {} reports for host {} for cracker {}!".format(len(candidates), ip_address, self.ip_address))
    #        result = candidates[0]
    #    elif len(candidates)==1:
    #        result = candidates[0]
    #    else:
    #        result = None
    #    return result

    # Must be in DB already
    def save(self, txn):
        try:
            txn.execute("UPDATE crackers SET first_time=?, latest_time=?, total_reports=? WHERE ip_address=?", (self.first_time, self.latest_time, self.total_reports, self.ip_address))
        except:
            print("Error in UPDATE")
        print("Saved cracker {}".format(self.ip_address))

def get_cracker(txn, ip_address):
        txn.execute("SELECT id, ip_address, first_time, latest_time, total_reports FROM crackers WHERE ip_address=?", (ip_address,))
        result = txn.fetchone()
        if result:
            cracker = Cracker(result[1])
            cracker.id = result[0]
            cracker.first_time = result[2]
            cracker.latest_time = result[3]
            cracker.total_reports = result[4]
        else:
            cracker = Cracker(ip_address)
            txn.execute("INSERT INTO crackers (ip_address,first_time,latest_time,total_reports) VALUES (?,?,?,?)",
            (ip_address,cracker.first_time, cracker.latest_time, cracker.total_reports))
            cracker.id = txn.lastrowid
        return cracker

def get_all_crackers(txn):
        txn.execute("SELECT ip_address, first_time, latest_time, total_reports FROM crackers")
        results = txn.fetchall()
        all = []
        if results:
            for r in results:
                cracker = Cracker(r[0])
                cracker.first_time = r[1]
                cracker.latest_time = r[2]
                cracker.total_reports = r[3]
                all.append(cracker)
        else:
            return []

class Report():
    def __init__(self, cracker, ip_address):
        self.cracker_id = cracker.id
        self.ip_address = ip_address
        self.first_report_time = datetime.now()
        self.latest_report_time = self.first_report_time

    def latest_total_resiliency(self):
        return self.latest_report_time - self.first_report_time

    def save(self,txn):
        txn.execute("""UPDATE reports 
            SET first_report_time=?, latest_report_time=? 
            WHERE cracker_id=? AND ip_address=?""", 
            (self.first_report_time, self.latest_report_time, self.cracker_id, self.ip_address))

def get_report_for_cracker(txn, cracker, report_ip_address):
    txn.execute("""SELECT first_report_time,latest_report_time
        FROM reports 
        WHERE reports.cracker_id = ? AND reports.ip_address = ?""", 
        (cracker.id,report_ip_address))
    result = txn.fetchone()
    if result is None:
        report = Report(cracker, report_ip_address)
        txn.execute("INSERT INTO reports (cracker_id, ip_address, first_report_time, latest_report_time) VALUES (?,?,?,?)", (cracker.id,
            report_ip_address, report.first_report_time, report.latest_report_time))
        return report
    else:
        report = Report(cracker,report_ip_address)
        report.first_report_time = result[0]
        report.latest_report_time = result[1]
        return report
