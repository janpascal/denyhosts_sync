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

from twistar.dbobject import DBObject

class Cracker(DBObject):
    HASMANY=['reports']

    def __str__(self):
        return "Cracker({},{},{},{},{},{})".format(self.id,self.ip_address,self.first_time,self.latest_time,self.resiliency,self.total_reports,self.current_reports)

class Report(DBObject):
    BELONGSTO=['cracker']

    def __str__(self):
        return "Report({},{},{},{})".format(self.id,self.ip_address,self.first_report_time,self.latest_report_time)

class Legacy(DBObject):
    TABLENAME="legacy"
    pass

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
