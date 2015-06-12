from datetime import datetime
import time

class Cracker():
    def __init__(self, ip_address):
        self.ip_address = ip_address
        self.first_time = datetime.now()
        self.latest_time = self.first_time
        self.total_reports = 0
        self.reports = []

    def add_report(self, ip_address):
        self.latest_time = datetime.now()
        self.total_reports += 1
        report = self.find_report(ip_address)
        if report is None:
            report = Report(ip_address)
            self.reports.append(report)
        report.latest_report_time = datetime.now();

    def resiliency(self):
        return self.latest_time - self.first_time

    def current_reports(self):
        return len(self.reports)

    def find_report(self, ip_address):
        candidates = [report for report in self.reports if
            report.ip_address == ip_address]
        if len(candidates)>1:
            print("Error, {} reports for host {} for cracker {}!".format(len(candidates), ip_address, self.ip_address))
            result = candidates[0]
        elif len(candidates)==1:
            result = candidates[0]
        else:
            result = None
        return result

class Report():
    def __init__(self, ip_address):
        self.ip_address = ip_address
        self.first_report_time = datetime.now()
        self.latest_report_time = self.first_report_time

    def latest_total_resiliency(self):
        return self.latest_report_time - self.first_report_time

