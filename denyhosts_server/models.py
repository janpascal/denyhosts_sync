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

import logging

from tortoise.models import Model
from tortoise import fields

class InfoItem(Model):
    key = fields.CharField(64, pk=True)
    value = fields.TextField()

    class Meta:
        table="info"    

class Cracker(Model):
    ip_address = fields.CharField(15)
    first_time = fields.IntField()
    latest_time = fields.IntField()
    resiliency = fields.IntField()
    total_reports = fields.IntField()
    current_reports = fields.IntField()

    def __str__(self):
        return "Cracker({},{},{},{},{},{})".format(self.id,self.ip_address,self.first_time,self.latest_time,self.resiliency,self.total_reports,self.current_reports)

    class Meta:
        table="crackers"    

class Report(Model):
    cracker = fields.ForeignKeyField('models.Cracker', related_name='reports')
    ip_address = fields.CharField(15)
    first_report_time = fields.IntField()
    latest_report_time = fields.IntField()

    def __str__(self):
        return "Report({},{},{},{})".format(self.id,self.ip_address,self.first_report_time,self.latest_report_time)

    class Meta:
        table="reports"    


class HistoryItem(Model):
    date = fields.DateField()
    num_reports = fields.IntField()
    num_contributors = fields.IntField()
    num_reported_hosts = fields.IntField()

    class Meta:
        table="history"    


class CountryHistoryItem(Model):
    country_code = fields.CharField(5, pk=True)
    country = fields.CharField(50)
    num_reports = fields.IntField()

    class Meta:
        table="country_history"    

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
