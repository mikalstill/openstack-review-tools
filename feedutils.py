#!/usr/bin/python

# Helpers for producing data feeds

import cgi
import datetime
import json
import random
import sys
import time
import MySQLdb

import sql

def SendPacket(packet):
    packet['timestamp'] = int(time.time())
    print json.dumps(packet)
    sys.stdout.flush()


def GetCursor():
    # Read config from a file
    with open('/srv/config/summaryfeed') as f:
        flags = json.loads(f.read())

    db = MySQLdb.connect(user = flags['dbuser'],
                         db = flags['dbname'],
                         passwd = flags['dbpassword'])
    cursor = db.cursor(MySQLdb.cursors.DictCursor)
    return cursor


def SendGroups(cursor):
    groups = []
    cursor.execute('select * from groups;')
    for row in cursor:
      groups.append([row['name'], row['members'].split(' ')])
    SendPacket({'type': 'groups',
                'payload': groups})

def SendReviewers(cursor, window_size):
    one_day = datetime.timedelta(days=1)
    start_of_window = datetime.datetime.now()
    start_of_window -= one_day * window_size

    all_reviewers = []
    cursor.execute('select distinct(username), max(day) from summary '
                   'where day > date(%s) group by username;'
                   % sql.FormatSqlValue('timestamp', start_of_window))
    for row in cursor:
      all_reviewers.append((row['username'], row['max(day)'].isoformat()))
    SendPacket({'type': 'users-all',
                'payload': all_reviewers})


def SendKeepAlive():
    SendPacket({'type': 'keepalive'})


def SendDebug(message):
    SendPacket({'type': 'debug',
                'payload': message})
