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


def ParseReviewList(db, component, status):
  keys = []
  values = {}
  for l in dbcachingexecute.Execute(db, time.time(),
                                    'gerrit_query',
                                    'ssh -i ~/.ssh/id_gerrit '
                                    'review.openstack.org gerrit query %s',
                                    'status:%s project:%s' %(status,
                                                             component),
                                    cleanup=True):
    l = l.strip().rstrip()

    if len(l) == 0 and values and 'subject' in values:
      description = []
      for key in keys:
        v = values[key]

        if key == 'url':
          description.append('&lt;b&gt;%s:&lt;/b&gt; '
                             '&lt;a href="%s"&gt;%s&lt;/a&gt;'
                             %(key, v, v))
        else:
          description.append('&lt;b&gt;%s:&lt;/b&gt; %s' %(key, v))

      values['description'] = '&lt;br/&gt;'.join(description)
      values['component'] = component
      yield values

      values = {}
      keys = []

    elif l.startswith('change '):
      values['change'] = ' '.join(l.split(' ')[1:])

    else:
      elems = l.split(': ')
      values[elems[0]] = ': '.join(elems[1:])
      if elems[0] not in keys:
        keys.append(elems[0])


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
        cursor.execute('insert ignore into reviews '
                       '(changeid, username, timestamp, component) values '
                       '("%s", "%s", %s, "%s");'
                       %(d['id'], review['by'].get('username', 'unknown'),
                         sql.FormatSqlValue('timestamp', updated_at),
                         component))
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
