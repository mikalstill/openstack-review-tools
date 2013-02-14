#!/usr/bin/python

# Take gerrit status feeds and turn them into an RSS feed

import sys
sys.path.append('/data/src/stillhq_public/trunk/python/')

import base64
import datetime
import gflags
import json
import re
import time
import MySQLdb

import dbcachingexecute
import sql


FLAGS = gflags.FLAGS
gflags.DEFINE_string('dbuser', 'openstack', 'DB username')
gflags.DEFINE_string('dbname', 'openstack_gerrit', 'DB name')
gflags.DEFINE_string('dbpassword', '', 'DB password')


def Reviews(db, component):
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
        # Deliberately leave the timezone alone here so its consistant with
        # reports others generate.
        updated_at = datetime.datetime.fromtimestamp(review['grantedOn'])
        username = review['by'].get('username', 'unknown')
        timestamp = sql.FormatSqlValue('timestamp', updated_at)
        cursor.execute('insert ignore into reviews '
                       '(changeid, username, timestamp, day, component) '
                       'values ("%s", "%s", %s, date(%s), "%s");'
                       %(d['id'], username, timestamp, timestamp, component))
        if cursor.rowcount > 0:
          # This is a new review
          print 'New review from %s' % username
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
