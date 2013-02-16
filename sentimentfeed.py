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
    initial_size = 30
    one_day = datetime.timedelta(days=1)
    last_timestamp = datetime.datetime(1970, 1, 1)

    feedutils.SendGroups(cursor)
    feedutils.SendReviewers(cursor, initial_size)
    feedutils.SendPacket({'type': 'users-present',
                          'payload': showusers})

    for username in showusers:
        day = datetime.datetime.now()
        day = datetime.datetime(day.year, day.month, day.day)
        day -= one_day * (initial_size - 1)
        timestamp = sql.FormatSqlValue('timestamp', day)

        cursor.execute('select *, date(timestamp) from reviews where '
                       'username="%s" and timestamp > %s '
                       'order by timestamp asc;'
                       %(username, timestamp))
        for row in cursor:
            packet = {'type': 'initial-user-review',
                      'user': username,
                      'day': row['timestamp'].isoformat(),
                      'payload': row['score']}
            feedutils.SendPacket(packet)

            if row['timestamp'] > last_timestamp:
                last_timestamp = row['timestamp']

    feedutils.SendPacket({'type': 'initial-user-reviews-ends'})

    # Then dump updates as they happen
    while True:
        time.sleep(60)

        # Rebuild the DB connection in case the DB went away
        cursor = feedutils.GetCursor()
	feedutils.SendKeepAlive()
        feedutils.SendDebug('Querying for updates after %s, server time %s'
                            %(last_timestamp, datetime.datetime.now()))

        for username in showusers:
            timestamp = sql.FormatSqlValue('timestamp', last_timestamp)
            cursor.execute('select * from reviews where '
                           'username="%s" and timestamp > %s '
                           'order by timestamp asc;'
                           %(username, timestamp))
            for row in cursor:
                packet = {'type': 'update-user-review',
                          'user': username,
                          'day': row['timestamp'].isoformat(),
                          'payload': row['score']}
                feedutils.SendPacket(packet)

                if row['timestamp'] > last_timestamp:
                    last_timestamp = row['timestamp']

