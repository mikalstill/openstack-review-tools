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

import dbcachingexecute
import feedutils
import sql


def Reviews(component):
    cursor = feedutils.GetCursor()
    for l in dbcachingexecute.Execute(time.time() - 60,
                                      'gerrit_query_approvals_json',
                                      ('ssh -i ~/.ssh/id_gerrit '
                                       'review.openstack.org gerrit query '
                                       'project:%s '
                                       '--all-approvals --patch-sets '
                                       '--format JSON'),
                                      component, cleanup=True):

      try:
          d = json.loads(l)
      except:
          continue

      if d.has_key('id'):
          b64 = base64.encodestring(l)
          checksum = hashlib.sha1(l).hexdigest()
          last_updated = datetime.datetime.fromtimestamp(d['lastUpdated'])
          timestamp = sql.FormatSqlValue('timestamp', last_updated)
          insert = ('insert ignore into changes (changeid, timestamp, parsed, '
                    'checksum) values ("%s", %s, "%s", "%s");'
                    %(d['id'], timestamp, b64, checksum))
          cursor.execute(insert)
          if cursor.rowcount == 0:
              cursor.execute('select * from changes where changeid="%s";'
                             % d['id'])
              stored_checksum = cursor.fetchone()['checksum']
              if checksum != stored_checksum:
                  cursor.execute('delete from changes where changeid="%s";'
                                 % d['id'])
                  cursor.execute(insert)
          cursor.execute('commit;')

      for ps in d.get('patchSets', {}):
          patchset = ps.get('number')

          for review in ps.get('approvals', []):
              # Deliberately leave the timezone alone here so its consistant
              # with reports others generate.
              updated_at = datetime.datetime.fromtimestamp(review['grantedOn'])
              username = review['by'].get('username', 'unknown')

              if username in ['jenkins', 'smokestack']:
                  continue

              timestamp = sql.FormatSqlValue('timestamp', updated_at)
              score = review.get('value', 0)
              cursor.execute('insert ignore into reviews '
                             '(changeid, username, timestamp, day, component, '
                             'patchset, score) '
                             'values ("%s", "%s", %s, date(%s), "%s", %s, %s);'
                             %(d['id'], username, timestamp, timestamp,
                               component, patchset, score))
              if cursor.rowcount > 0:
                  # This is a new review, we assume we're the only writer
                  print 'New review from %s' % username
                  cursor.execute('select * from reviewsummary where '
                                 'username="%s" and day=date(%s);'
                                 %(username, timestamp))
                  if cursor.rowcount > 0:
                      row = cursor.fetchone()
                      try:
                          summary = json.loads(row['data'])
                      except Exception, e:
                          print 'Could not decode summary "%s": %s' %(row['data'], e)
                          summary = {}
                  else:
                      summary = {}

                  summary.setdefault(component, 0)
                  summary.setdefault('__total__', 0)
                  summary[component] += 1
                  summary['__total__'] += 1

                  cursor.execute('delete from reviewsummary where '
                                 'username="%s" and day=date(%s);'
                                 %(username, timestamp))
                  cursor.execute('insert into reviewsummary'
                                 '(day, username, data, epoch) '
                                 'values (date(%s), "%s", \'%s\', %d);'
                                 %(timestamp, username,
                                   json.dumps(summary),
                                   int(time.time())))

              cursor.execute('commit;')


if __name__ == '__main__':
    for l in dbcachingexecute.Execute(time.time() - 60,
                                      'gerrit_projects',
                                      ('ssh -i ~/.ssh/id_gerrit '
                                       'review.openstack.org gerrit %s'),
                                      'ls-projects', cleanup=True):
        l = l.rstrip()
        print 'Project: %s' % l
        Reviews(l)

