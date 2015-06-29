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

import config

_schema_version = 3

def _remove_tables(txn):
    print("Removing all data from database and removing tables")
    txn.execute("DROP TABLE IF EXISTS info")
    txn.execute("DROP TABLE IF EXISTS crackers")
    txn.execute("DROP TABLE IF EXISTS reports")

def _evolve_database_v0(txn, dbtype):
    if dbtype=="sqlite3":
        autoincrement="AUTOINCREMENT"
    elif dbtype=="MySQLdb":
        autoincrement="AUTO_INCREMENT"

    txn.execute("""CREATE TABLE crackers (
        id INTEGER PRIMARY KEY {},
        ip_address CHAR(15), 
        first_time INTEGER, 
        latest_time INTEGER, 
        total_reports INTEGER, 
        current_reports INTEGER
    )""".format(autoincrement))
    txn.execute("CREATE UNIQUE INDEX cracker_ip_address ON crackers (ip_address)")

    txn.execute("""CREATE TABLE reports(
        id INTEGER PRIMARY KEY {}, 
        cracker_id INTEGER, 
        ip_address CHAR(15), 
        first_report_time INTEGER, 
        latest_report_time INTEGER
    )""".format(autoincrement))
    txn.execute("CREATE INDEX report_first_time ON reports (first_report_time)")
    txn.execute("CREATE UNIQUE INDEX report_cracker_ip ON reports (cracker_id, ip_address)")
    txn.execute("CREATE INDEX report_cracker_first ON reports (cracker_id, first_report_time)")

    txn.execute("""CREATE TABLE legacy(
        id INTEGER PRIMARY KEY {}, 
        ip_address CHAR(15), 
        retrieved_time INTEGER
    )""".format(autoincrement))
    txn.execute("CREATE UNIQUE INDEX legacy_ip ON legacy (ip_address)")
    txn.execute("CREATE INDEX legacy_retrieved ON legacy (retrieved_time)")

def _evolve_database_v1(txn, dbtype):
    txn.execute("""CREATE TABLE info (
        `key` TEXT PRIMARY KEY,
        `value` TEXT
    )""")
    if dbtype=="sqlite3":
        txn.execute('INSERT INTO info VALUES ("schema_version", ?)', (str(_schema_version),))
    elif dbtype=="MySQLdb":
        txn.execute('INSERT INTO info VALUES ("schema_version", %s)', (str(_schema_version),))
    txn.execute('INSERT INTO info VALUES ("last_legacy_sync", 0)')

def _evolve_database_v2(txn, dbtype):
    txn.execute("ALTER TABLE crackers ADD resiliency INTEGER")
    txn.execute("CREATE INDEX cracker_qual ON crackers (current_reports, resiliency, latest_time, first_time)")
    txn.execute("CREATE INDEX cracker_first ON crackers (first_time)")
    txn.execute("UPDATE crackers SET resiliency=latest_time-first_time")

def _evolve_database_v3(txn, dbtype):
    if dbtype=="sqlite3":
        txn.execute("DROP INDEX cracker_qual")
    elif dbtype=="MySQLdb":
        txn.execute("ALTER TABLE crackers DROP INDEX cracker_qual")
    txn.execute("CREATE INDEX cracker_qual ON crackers (latest_time, current_reports, resiliency, first_time)")

def _evolve_database(txn):
    print("Evolving database")
    dbtype = config.dbtype

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
        _evolve_database_v0(txn, dbtype)
        _evolve_database_v1(txn, dbtype)

    if current_version < 2:
        print("Evolving database to version 2, this may take a while...")
        _evolve_database_v2(txn, dbtype)

    if current_version < 3:
        print("Evolving database to version 3, this may take a while...")
        _evolve_database_v3(txn, dbtype)

    if current_version > _schema_version:
        print("Illegal database schema {}".format(current_version))

    if dbtype=="sqlite3":
        txn.execute('UPDATE info SET `value`=? WHERE `key`="schema_version"', (str(_schema_version),))
    elif dbtype=="MySQLdb":
        txn.execute('UPDATE info SET `value`=%s WHERE `key`="schema_version"', (str(_schema_version),))

    print("Updated database schema, current version is {}".format(_schema_version))

def evolve_database():
    return Registry.DBPOOL.runInteraction(_evolve_database)

@inlineCallbacks
def clean_database():
    yield Registry.DBPOOL.runInteraction(_remove_tables)
    yield Registry.DBPOOL.runInteraction(_evolve_database)
    returnValue(0)


@inlineCallbacks
def check_database_version():
    try:
        rows = yield Registry.DBPOOL.runQuery('SELECT `value` FROM `info` WHERE `key`="schema_version"')
        if rows is not None:
            current_version = int(rows[0][0])
        else:
            print("No schema version in database")
            current_version = 0
    except:
        current_version = 0

    if current_version != _schema_version:
        logging.debug("Wrong database schema {}, expecting {}, exiting".format(current_version, _schema_version))
        print("Wrong database schema {}, expecting {}, exiting".format(current_version, _schema_version))
        from twisted.internet import reactor
        reactor.stop()
    else:
        logging.info("Database schema is up to date (version {})".format(current_version))
        returnValue(current_version)

# FIXME Not the proper way. What if there's a question mark somewhere
# else in the query?
def run_query(query, *args):
    if config.dbtype == "MySQLdb":
        query = query.replace('?', '%s')
    elif config.dbtype == "sqlite3":
        pass
    else:
        print("unsupported database {}".format(config.dbtype))
    return Registry.DBPOOL.runQuery(query, args)

def run_operation(query, *args):
    if config.dbtype == "MySQLdb":
        query = query.replace('?', '%s')
    elif config.dbtype == "sqlite3":
        pass
    else:
        print("unsupported database {}".format(config.dbtype))
    return Registry.DBPOOL.runOperation(query, args)
        
#def runGetPossibleQualifyingCrackerQuery(min_reports, min_resilience, previous_timestamp):
#    if config.dbtype == "MySQLdb":
#        return Registry.DBPOOL.runQuery("""
#            SELECT DISTINCT c.id, c.ip_address 
#            FROM crackers c 
#            JOIN reports r ON r.cracker_id=c.id
#            WHERE (c.current_reports >= %s) AND 
#                (c.latest_time - c.first_time >= %s)
#                AND (c.latest_time >= %s)
#            ORDER BY c.first_time DESC
#        """, 
#        [min_reports, min_resilience, previous_timestamp])
#    elif config.dbtype == "sqlite3":
#        return Registry.DBPOOL.runQuery("""
#            SELECT DISTINCT c.id, c.ip_address 
#            FROM crackers c 
#            JOIN reports r ON r.cracker_id=c.id
#            WHERE (c.current_reports >= ?) AND 
#                (c.latest_time - c.first_time >= ?)
#                AND (c.latest_time >= ?)
#            ORDER BY c.first_time DESC
#        """, 
#        [min_reports, min_resilience, previous_timestamp])
#    else:
#        return Fault("error")
