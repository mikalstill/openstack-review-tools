#!/usr/bin/python

# Rebuild the triage summary table.

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
    triage_cursor = feedutils.GetCursor()

    users_cursor.execute('select distinct(username) from bugtriage;')
    for user_row in users_cursor:
        print user_row['username']
        dates_cursor.execute('select distinct(date(timestamp)) '
                             'from bugtriage where username = "%s";'
                             % user_row['username'])
        for date_row in dates_cursor:
            print '  %s' % date_row['(date(timestamp))']
            timestamp = sql.FormatSqlValue('timestamp',
                                           date_row['(date(timestamp))'])
            summary = {'__total__': 0}

            triage_cursor.execute('select * from bugtriage where '
                                   'username = "%s" and date(timestamp) = %s '
                                   'order by timestamp asc;'
                                   %(user_row['username'], timestamp))
            for triage in triage_cursor:
                summary.setdefault(triage['component'], 0)
                summary[triage['component']] += 1
                summary['__total__'] += 1

            epoch = time.mktime(triage['timestamp'].timetuple())
            triage_cursor.execute('delete from bugtriagesummary where '
                                   'username="%s" and day=date(%s);'
                                   %(user_row['username'], timestamp))
            triage_cursor.execute('insert into bugtriagesummary'
                                   '(day, username, data, epoch) '
                                   'values (date(%s), "%s", \'%s\', %d);'
                                   %(timestamp, user_row['username'],
                                     json.dumps(summary), epoch))
            triage_cursor.execute('commit;')


if __name__ == '__main__':
    RebuildSummary()
