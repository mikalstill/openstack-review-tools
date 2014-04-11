#!/usr/bin/python

# Scrape review information from gerrit

import base64
import datetime
import hashlib
import json
import re
import sys
import time
import MySQLdb
import urllib

import dbcachingexecute
import feedutils
import sql


def Reviews(day):
    cursor = feedutils.GetCursor()

    url = ('http://www.rcbops.com/gerrit/merged/%04d/%d/%d_reviews.json'
           % (day.year, day.month, day.day))
    print url

    remote = urllib.urlopen(url)
    d = json.loads(''.join(remote.readlines()))
    
    for l in remote.readlines():
        try:
            d = json.loads(l)
        except:
            continue

    for reviewer in d:
        for review in d['reviewer']:
            cursor.execute('select * from reviews where changeid="%s" and '
                           'username="%s" and component="%s" and '
                           'patchset=%s and score=%s;'
                           %(review['id'], reviewer, review['project'],
                             review['patchset'], review['value']))
            if cursor.rowcount == 0:
                cursor.execute('insert into reviews (changeid, username, '
                               'component, patchset, score, timestamp, day) '
                               'values("%s", "%s", "%s", %s, %s, now(), '
                               'date(now));')
                cursor.execute('commit;')

                summary = {}
                cursor.execute('select * from reviews where '
                               'username = "%s" and '
                               'date(timestamp) = date(now()) '
                               'order by timestamp asc;'
                               % reviewer)
                for review in cursor:
                    summary.setdefault(review['component'], 0)
                    summary[review['component']] += 1
                    summary['__total__'] += 1

                epoch = time.mktime(review['timestamp'].timetuple())
                cursor.execute('delete from reviewsummary where '
                               'username="%s" and day=date(%s);'
                               %(user_row['username'], timestamp))
                cursor.execute('insert into reviewsummary'
                               '(day, username, data, epoch) '
                               'values (date(%s), "%s", \'%s\', %d);'
                               %(timestamp, reviewer,
                                 json.dumps(summary), epoch))
                cursor.execute('commit;')

if __name__ == '__main__':
    Reviews(datetime.datetime.now())

