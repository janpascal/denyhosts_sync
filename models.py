import time

class Cracker():
    def __init__(self, id, ip_address, first_time, latest_time, total_reports, current_reports):
        self.id = id
        self.ip_address = ip_address
        self.first_time = first_time
        self.latest_time = latest_time
        self.total_reports = total_reports
        self.current_reports = current_reports

    def add_report(self, txn, ip_address):
        report = get_report_for_cracker(txn, self.id, ip_address)
        report.latest_report_time = time.time();
        report.save(txn)

        self.total_reports += 1
        self.latest_time = report.latest_report_time
        # FIXME: query shouldn't be necessary
        self.current_reports = get_count_reports_for_cracker(txn, self.id)

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
            txn.execute("""UPDATE crackers 
                SET first_time=?, latest_time=?, total_reports=?, current_reports=? 
                WHERE ip_address=?""", 
                (self.first_time, self.latest_time, self.total_reports, self.current_reports, self.ip_address))
        except:
            print("Error in UPDATE")
        print("Saved cracker {}".format(self.ip_address))

    def __str__(self):
        return "Cracker({},{},{},{},{},{})".format(self.id,self.ip_address,self.first_time,self.latest_time,self.total_reports,self.current_reports)

def new_cracker(txn, ip_address):
    now =time.time()
    txn.execute("""INSERT INTO crackers 
        (ip_address,first_time,latest_time,total_reports,current_reports) 
        VALUES (?,?,?,?,?)""",
            (ip_address,now, now, 0, 0)
    )
    return Cracker(txn.lastrowid, ip_address, now, now, 0, 0)

def get_cracker(txn, ip_address):
        txn.execute("SELECT id, ip_address, first_time, latest_time, total_reports, current_reports FROM crackers WHERE ip_address=?", (ip_address,))
        result = txn.fetchone()
        if result:
            cracker = Cracker(result[0], result[1], result[2], result[3], result[4], result[5])
            print("Cracker from database: {}".format(cracker))
        else:
            cracker = new_cracker(txn, ip_address)
            print("Created new cracker: {}".format(cracker))
        return cracker

def get_all_crackers(txn):
        txn.execute("SELECT id, ip_address, first_time, latest_time, total_reports, current_reports FROM crackers")
        results = txn.fetchall()
        all = []
        if results:
            for r in results:
                cracker = Cracker(r[0], r[1], r[2], r[3], r[4], r[5])
                all.append(cracker)
        return all

class Report():
    def __init__(self, id, cracker_id, ip_address, first_report_time, latest_report_time):
        self.id = id
        self.cracker_id = cracker_id
        self.ip_address = ip_address
        self.first_report_time = first_report_time
        self.latest_report_time = latest_report_time

    def latest_total_resiliency(self):
        # Fails
        return self.latest_report_time - self.cracker.first_report_time

    def save(self,txn):
        txn.execute("""UPDATE reports 
            SET cracker_id=?, ip_address=?, first_report_time=?, latest_report_time=?
            WHERE id=?""", 
            (self.cracker_id, self.ip_address, self.first_report_time, self.latest_report_time, self.id))

def new_report(txn, cracker_id, ip_address):
    now = time.time()
    txn.execute("""INSERT INTO reports 
        (cracker_id,ip_address,first_report_time,latest_report_time) 
        VALUES (?,?,?,?)""",
            (cracker_id,ip_address,now, now)
    )
    return Report(txn.lastrowid, cracker_id, ip_address, now, now)

def get_report_for_cracker(txn, cracker_id, report_ip_address):
    txn.execute("""SELECT id, first_report_time,latest_report_time
        FROM reports 
        WHERE reports.cracker_id = ? AND reports.ip_address = ?""", 
        (cracker_id,report_ip_address))
    r = txn.fetchone()
    if r is None:
        report = new_report(txn, cracker_id, report_ip_address)
    else:
        report = Report(r[0], cracker_id, report_ip_address, r[1], r[2])
    return report

def get_all_reports_for_cracker(txn, cracker_id):
    txn.execute("""SELECT id, ip_address, first_report_time,latest_report_time
        FROM reports 
        WHERE reports.cracker_id = ?""", 
        (cracker_id,))
    results = txn.fetchall()
    all = []
    if results:
        for r in results:
            report = Report(r[0], cracker_id, r[1], r[2], r[3])
            all.append(report)
    return all

def get_count_reports_for_cracker(txn, cracker_id):
    txn.execute("""SELECT COUNT(*) 
        FROM reports 
        WHERE reports.cracker_id = ?""", 
        (cracker_id,))
    results = txn.fetchone()
    if results:
        return results[0]
    else:
        return 0

def get_qualifying_crackers(txn, N, T, S1):
    # Initial version, see
    # https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=622697
    # for algorithm. 
    # Not complete yet!
    txn.execute("""
            SELECT DISTINCT c.id, c.ip_address 
            FROM crackers c 
            JOIN reports r ON r.cracker_id=c.id
            WHERE (c.current_reports >= ?) AND 
                (c.latest_time - c.first_time >= ?)
                AND (c.latest_time >= ?)
            ORDER BY c.first_time DESC
            LIMIT ?
        """, 
        (N, T, S1, 50)
    )
    results = txn.fetchall()
    if results is None:
        return []
    else:
        return [r[1] for r in results]

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4

