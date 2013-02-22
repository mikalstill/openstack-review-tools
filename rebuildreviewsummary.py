#!/usr/bin/python

# Rebuild the review summary table.

import base64
import datetime
import hashlib
import json
import re
import sys
import time
import MySQLdb

import dbcachingexecute
import feedutils
import sql


def RebuildSummary():
    users_cursor = feedutils.GetCursor()
    dates_cursor = feedutils.GetCursor()
    reviews_cursor = feedutils.GetCursor()

    users_cursor.execute('select distinct(username) from reviews;')
    for user_row in users_cursor:
        print user_row['username']
        dates_cursor.execute('select distinct(date(timestamp)) '
                             'from reviews where username = "%s";'
                             % user_row['username'])
        for date_row in dates_cursor:
            print '  %s' % date_row['(date(timestamp))']
            timestamp = sql.FormatSqlValue('timestamp',
                                           date_row['(date(timestamp))'])
            summary = {'__total__': 0}

            reviews_cursor.execute('select * from reviews where '
                                   'username = "%s" and date(timestamp) = %s '
                                   'order by timestamp asc;'
                                   %(user_row['username'], timestamp))
            for review in reviews_cursor:
                summary.setdefault(review['component'], 0)
                summary[review['component']] += 1
                summary['__total__'] += 1

            epoch = time.mktime(review['timestamp'].timetuple())
            cursor.execute('delete from reviewsummary where '
                           'username="%s" and day=date(%s);'
                           %(username, timestamp))
            cursor.execute('insert into reviewsummary'
                           '(day, username, data, epoch) '
                           'values (date(%s), "%s", \'%s\', %d);'
                           %(timestamp, username, json.dumps(summary), epoch))


if __name__ == '__main__':
    RebuildSummary()
