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
from twistar.registry import Registry

def initdb():
    logging.info("Creating tables")

    def run_initdb(txn):
        txn.execute("DROP TABLE IF EXISTS crackers")
        txn.execute("""CREATE TABLE crackers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_address TEXT, 
            first_time INTEGER, 
            latest_time INTEGER, 
            total_reports INTEGER, 
            current_reports INTEGER
        )""")
        txn.execute("DROP INDEX IF EXISTS cracker_ip_address")
        txn.execute("CREATE UNIQUE INDEX cracker_ip_address ON crackers (ip_address)")

        txn.execute("DROP TABLE IF EXISTS reports")
        txn.execute("""CREATE TABLE reports(
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            cracker_id INTEGER, 
            ip_address TEXT, 
            first_report_time INTEGER, 
            latest_report_time INTEGER
        )""")
        txn.execute("DROP INDEX IF EXISTS report_first_time")
        txn.execute("CREATE INDEX report_first_time ON reports (first_report_time)")
        txn.execute("DROP INDEX IF EXISTS report_cracker_ip")
        txn.execute("CREATE UNIQUE INDEX report_cracker_ip ON reports (cracker_id, ip_address)")
        txn.execute("DROP INDEX IF EXISTS report_cracker_first")
        txn.execute("CREATE INDEX report_cracker_first ON reports (cracker_id, first_report_time)")

    return Registry.DBPOOL.runInteraction(run_initdb)
