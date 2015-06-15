#!/usr/bin/env python
import sqlite3

from twisted.web import server
from twisted.enterprise import adbapi

import views

if __name__ == '__main__':
    print("Creating tables")
    db = sqlite3.connect("denyhosts.sqlite")
    db.execute("DROP TABLE IF EXISTS crackers")
    db.execute("""CREATE TABLE crackers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ip_address TEXT, 
        first_time INTEGER, 
        latest_time INTEGER, 
        total_reports INTEGER, 
        current_reports INTEGER
    )""")
    db.execute("DROP INDEX IF EXISTS cracker_ip_address")
    db.execute("CREATE INDEX cracker_ip_address ON crackers (ip_address)")
    db.execute("DROP TABLE IF EXISTS reports")
    db.execute("CREATE TABLE reports(id INTEGER PRIMARY KEY AUTOINCREMENT, cracker_id INTEGER, ip_address TEXT, first_report_time INTEGER, latest_report_time INTEGER)")
    db.close()
    dbpool = adbapi.ConnectionPool("sqlite3", 'denyhosts.sqlite')
    from twisted.internet import reactor
    r = views.Server(dbpool)
    reactor.listenTCP(8000, server.Site(r))
    print("Starting reactor...")
    reactor.run()
    dbpool.close()

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
