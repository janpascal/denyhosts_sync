from datetime import datetime
import time

from storm.locals import *

class Cracker():
    __storm_table__ = "cracker"
    ip_address = Unicode(primary=True)
    first_time = DateTime()
    latest_time = DateTime()
    total_reports = Int()

    def __init__(self, ip_address):
        self.ip_address = ip_address
        self.first_time = datetime.now()
        self.latest_time = self.first_time
        self.total_reports = 0
        # self.reports = []

    def add_report(self, ip_address):
        self.latest_time = time.time()
        self.total_reports += 1
#        if main.root.self.

    def resiliency():
        return self.latest_time - self.first_time

    def current_reports():
        # return self.reports.size()
        return self.total_reports()

#    ip_address = models.GenericIPAddressField(unpack_ipv4=True, primary_key=True)
#    first_time = models.DateTimeField()
#    latest_time = models.DateTimeField()
#    resiliency = models.DurationField()
#    total_reports = models.IntegerField()
#    current_reports = models.IntegerField()
#
class Report():
    def __init__(self, ip_address):
        self.ip_address = ip_address
        self.first_report_time = datetime.now()
        self.latest_report_time = self.first_report_time
        self.latest_total_resiliency = 0
#    cracker = models.ForeignKey(Cracker, related_name="reports")
#
#    reporting_ip_address = models.GenericIPAddressField(unpack_ipv4=True, primary_key=True)
#    first_report_time = models.DateTimeField()
#    latest_report_time = models.DateTimeField()
#    latest_total_resiliency = models.DurationField()
#
