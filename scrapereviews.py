#!/usr/bin/python

# Take gerrit status feeds and turn them into an RSS feed

import base64
import datetime
import gflags
import json
import re
import sys
import time
import MySQLdb

import dbcachingexecute
import sql


FLAGS = gflags.FLAGS
gflags.DEFINE_string('dbuser', 'openstack', 'DB username')
gflags.DEFINE_string('dbname', 'openstack_gerrit', 'DB name')
gflags.DEFINE_string('dbpassword', '', 'DB password')


def Reviews(db, component):
    summaries = {}

    cursor = db.cursor(MySQLdb.cursors.DictCursor)
    for l in dbcachingexecute.Execute(db, time.time() - 300,
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

      for ps in d.get('patchSets', {}):
          for review in ps.get('approvals', []):
              # Deliberately leave the timezone alone here so its consistant
              # with reports others generate.
              updated_at = datetime.datetime.fromtimestamp(review['grantedOn'])
              username = review['by'].get('username', 'unknown')
              timestamp = sql.FormatSqlValue('timestamp', updated_at)
              cursor.execute('insert ignore into reviews '
                             '(changeid, username, timestamp, day, component) '
                             'values ("%s", "%s", %s, date(%s), "%s");'
                             %(d['id'], username, timestamp, timestamp,
                               component))
              if cursor.rowcount > 0:
                  # This is a new review, we assume we're the only writer
                  print 'New review from %s' % username
                  if not username in summaries:
                      cursor.execute('select * from summary where '
                                     'username="%s" and day=date(%s);'
                                     %(username, timestamp))
                      if cursor.rowcount > 0:
                          row = cursor.fetchone()
                          summaries[username] = json.loads(row['data'])
                      else:
                          summaries[username] = {}

                  summaries[username].setdefault(component, 0)
                  summaries[username].setdefault('__total__', 0)
                  summaries[username][component] += 1
                  summaries[username]['__total__'] += 1

                  cursor.execute('delete from summary where username="%s" '
                                 'and day=date(%s);'
                                 %(username, timestamp))
                  cursor.execute('insert into summary'
                                 '(day, username, data, epoch) '
                                 'values (date(%s), "%s", \'%s\', %d);'
                                 %(timestamp, username,
                                   json.dumps(summaries[username]),
                                   int(time.time())))

              cursor.execute('commit;')


if __name__ == '__main__':
    # Parse flags
    try:
        argv = FLAGS(sys.argv)

    except gflags.FlagsError, e:
        print 'Flags error: %s' % e
        print
        print FLAGS

    print 'DB connection: %s/%s to %s' %(FLAGS.dbuser, FLAGS.dbpassword,
                                         FLAGS.dbname)
    db = MySQLdb.connect(user = FLAGS.dbuser,
                         db = FLAGS.dbname,
                         passwd = FLAGS.dbpassword)

    Reviews(db, 'openstack/nova')
    Reviews(db, 'openstack/openstack-common')
    Reviews(db, 'openstack/oslo-incubator')
    Reviews(db, 'openstack/glance')
    Reviews(db, 'openstack/horizon')
    Reviews(db, 'openstack/keystone')
    Reviews(db, 'openstack/swift')
    Reviews(db, 'openstack/cinder')
