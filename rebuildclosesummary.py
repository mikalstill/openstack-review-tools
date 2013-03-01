#!/usr/bin/python

# Rebuild the close summary table.

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
    close_cursor = feedutils.GetCursor()

    users_cursor.execute('select distinct(username) from bugclose;')
    for user_row in users_cursor:
        print user_row['username']
        dates_cursor.execute('select distinct(date(timestamp)) '
                             'from bugclose where username = "%s";'
                             % user_row['username'])
        for date_row in dates_cursor:
            print '  %s' % date_row['(date(timestamp))']
            timestamp = sql.FormatSqlValue('timestamp',
                                           date_row['(date(timestamp))'])
            summary = {'__total__': 0}

            close_cursor.execute('select * from bugclose where '
                                   'username = "%s" and date(timestamp) = %s '
                                   'order by timestamp asc;'
                                   %(user_row['username'], timestamp))
            for close in close_cursor:
                summary.setdefault(close['component'], 0)
                summary[close['component']] += 1
                summary['__total__'] += 1

            epoch = time.mktime(close['timestamp'].timetuple())
            close_cursor.execute('delete from bugclosesummary where '
                                   'username="%s" and day=date(%s);'
                                   %(user_row['username'], timestamp))
            close_cursor.execute('insert into bugclosesummary'
                                   '(day, username, data, epoch) '
                                   'values (date(%s), "%s", \'%s\', %d);'
                                   %(timestamp, user_row['username'],
                                     json.dumps(summary), epoch))
            close_cursor.execute('commit;')


if __name__ == '__main__':
    RebuildSummary()
