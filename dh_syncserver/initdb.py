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
from twisted.internet.defer import inlineCallbacks, returnValue

_schema_version = 1

def _remove_tables(txn):
    print("Removing all data from database and removing tables")
    txn.execute("DROP TABLE IF EXISTS info")
    txn.execute("DROP TABLE IF EXISTS crackers")
    txn.execute("DROP TABLE IF EXISTS reports")

def _initdb(txn):
    print("Creating tables")
    txn.execute("""CREATE TABLE info (
        `key` TEXT PRIMARY KEY,
        `value` TEXT
    )""")
    txn.execute('INSERT INTO info VALUES ("schema_version", ?)', str(_schema_version))
    txn.execute('INSERT INTO info VALUES ("last_legacy_sync", 0)')

    txn.execute("""CREATE TABLE crackers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ip_address TEXT, 
        first_time INTEGER, 
        latest_time INTEGER, 
        total_reports INTEGER, 
        current_reports INTEGER
    )""")
    txn.execute("CREATE UNIQUE INDEX cracker_ip_address ON crackers (ip_address)")

    txn.execute("""CREATE TABLE reports(
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        cracker_id INTEGER, 
        ip_address TEXT, 
        first_report_time INTEGER, 
        latest_report_time INTEGER
    )""")
    txn.execute("CREATE INDEX report_first_time ON reports (first_report_time)")
    txn.execute("CREATE UNIQUE INDEX report_cracker_ip ON reports (cracker_id, ip_address)")
    txn.execute("CREATE INDEX report_cracker_first ON reports (cracker_id, first_report_time)")

    txn.execute("DROP TABLE IF EXISTS legacy")
    txn.execute("""CREATE TABLE legacy(
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        ip_address TEXT, 
        retrieved_time INTEGER
    )""")
    txn.execute("CREATE UNIQUE INDEX legacy_ip ON legacy (ip_address)")
    txn.execute("CREATE INDEX legacy_retrieved ON legacy (retrieved_time)")
    print("Database tables created")

def initdb():
    return Registry.DBPOOL.runInteraction(_initdb)

@inlineCallbacks
def clean_database():
    yield Registry.DBPOOL.runInteraction(_remove_tables)
    yield Registry.DBPOOL.runInteraction(_initdb)
    returnValue(0)

def _evolve_database(txn):
    try:
        txn.execute('SELECT `value` FROM info WHERE `key`="schema_version"')
        result = txn.fetchone()
        if result is not None:
            current_version = int(result[0])
        else:
            print("No schema version in database")
            current_version = 0
    except:
        print("No schema version in database")
        current_version = 0

    print("Current database schema is version {}".format(current_version))

    if current_version < 1:
        print("Evolving database to version 1")
        txn.execute("""CREATE TABLE info (
            `key` TEXT PRIMARY KEY,
            `value` TEXT
        )""")
        txn.execute('INSERT INTO info VALUES ("schema_version", ?)', str(_schema_version))
        txn.execute('INSERT INTO info VALUES ("last_legacy_sync", 0)')

    if current_version > _schema_version:
        print("Illegal database schema {}".format(current_version))

    txn.execute('UPDATE info SET `value`=? WHERE `key`="schema_version"', str(_schema_version))

    print("Updated database schema, current version is {}".format(_schema_version))

def evolve_database():
    print("Evolving database")
    return Registry.DBPOOL.runInteraction(_evolve_database)
