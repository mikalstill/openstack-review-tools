#!/usr/bin/python

# Take gerrit status feeds and turn them into an RSS feed

import cgi
import datetime
import json
import random
import sys
import time
import MySQLdb

import feedutils
import sql

if __name__ == '__main__':
    print 'Content-Type: text/plain\r'
    print '\r'
    sys.stdout.flush()

    showusers = ['mikalstill']
    form = cgi.FieldStorage()
    if form.has_key('reviewers'):
      showusers = form['reviewers'].value.lstrip(' ').split(' ')

    cursor = feedutils.GetCursor()

    # Fetch the last seven days of results to start off with
    last_time = 0
    initial_size = 30
    one_day = datetime.timedelta(days=1)

    feedutils.SendGroups(cursor)
    feedutils.SendReviewers(cursor, initial_size)
    feedutils.SendPacket({'type': 'users-present',
                          'payload': showusers})

    for username in showusers:
        day = datetime.datetime.now()
        day = datetime.datetime(day.year, day.month, day.day)

        day -= one_day * (initial_size - 1)
        for i in range(initial_size):
            timestamp = sql.FormatSqlValue('timestamp', day)
            cursor.execute('select * from summary where username="%s" and '
                           'day=date(%s);'
                           %(username, timestamp))
            packet = {'type': 'initial-user-summary',
                      'user': username,
                      'day': day.isoformat()}
            if cursor.rowcount > 0:
                row = cursor.fetchone()
                packet['payload'] = json.loads(row['data'])['__total__']
                packet['written-at'] = row['epoch']

                if row['epoch'] > last_time:
                    last_time = row['epoch']
            else:
                packet['payload'] = 0

            feedutils.SendPacket(packet)
            day += one_day

    feedutils.SendPacket({'type': 'initial-user-summary-ends'})

    # Then dump updates as they happen
    while True:
        time.sleep(60)

        # Rebuild the DB connection in case the DB went away
        cursor = feedutils.GetCursor()
	feedutils.SendKeepAlive()
        feedutils.SendDebug('Querying for updates after %d, server time %s'
                            %(last_time, datetime.datetime.now()))

        for username in showusers:
            cursor.execute('select * from summary where username="%s" and '
                           'epoch > %d;'
                           %(username, last_time))

            for row in cursor:
                feedutils.SendPacket({'type': 'update-user-summary',
                                      'user': username,
                                      'written-at': row['epoch'],
                                      'day': row['day'].isoformat(),
                                      'payload': json.loads(row['data'])['__total__']})

                if row['epoch'] > last_time:
                    last_time = row['epoch']
