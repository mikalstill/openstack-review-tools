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


def GetGroupMembers(cursor, groupname):
    members = []
    cursor.execute('select * from groups where name="%s";'
                   % groupname)
    if cursor.rowcount > 0:
      row = cursor.fetchone()
      for member in row['members'].split(' '):
        members.append(member)
    return members


def ResolveGroupMembers(cursor, usersliststring):
    showusers = []

    for userish in usersliststring.lstrip(' ').split(' '):
      if userish.startswith('g:'):
        for user in GetGroupMembers(cursor, userish.split(':')[1]):
          showusers.append(user)
      else:
        showusers.append(userish)

    if len(showusers) == 0:
      showusers = ['mikalstill']

    return showusers


def SendReviewers(cursor, window_size):
    SendUsers(cursor, window_size, 'reviewsummary')


def SendTriagers(cursor, window_size):
    SendUsers(cursor, window_size, 'bugtriagesummary')


def SendClosers(cursor, window_size):
    SendUsers(cursor, window_size, 'bugclosesummary')


def SendUsers(cursor, window_size, table):
    one_day = datetime.timedelta(days=1)
    start_of_window = datetime.datetime.now()
    start_of_window -= one_day * window_size

    all_reviewers = []
    cursor.execute('select distinct(username), max(day) from %s '
                   'where day > date(%s) group by username;'
                   %(table,
                     sql.FormatSqlValue('timestamp', start_of_window)))
    for row in cursor:
      all_reviewers.append((row['username'], row['max(day)'].isoformat()))
    SendPacket({'type': 'users-all',
                'payload': all_reviewers})


def SendKeepAlive():
    SendPacket({'type': 'keepalive'})


def SendDebug(message):
    SendPacket({'type': 'debug',
                'payload': message})
