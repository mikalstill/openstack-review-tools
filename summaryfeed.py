#!/usr/bin/python

# Take gerrit status feeds and turn them into an RSS feed

import datetime
import gflags
import json
import sys
import time
import MySQLdb

import sql

FLAGS = gflags.FLAGS
gflags.DEFINE_string('dbuser', 'openstack', 'DB username')
gflags.DEFINE_string('dbname', 'openstack_gerrit', 'DB name')
gflags.DEFINE_string('dbpassword', '', 'DB password')


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
    cursor = db.cursor(MySQLdb.cursors.DictCursor)

    # Fetch the last seven days of results to start off with
    day = datetime.datetime.now()
    one_day = datetime.timedelta(days=1)
    last_time = 0

    username = 'mikalstill'

    day -= one_day * 7
    for i in range(7):
        timestamp = sql.FormatSqlValue('timestamp', day)
        cursor.execute('select * from summary where username="%s" and '
                       'day=date(%s);'
                       %(username, timestamp))
        packet = {'type': 'initial-user-summary',
                  'timestamp': int(time.time()),
                  'user': username,
                  'day': day.strftime('%Y-%m-%d')}
        if cursor.rowcount > 0:
            row = cursor.fetchone()
            packet['payload'] = json.loads(row['data'])

            if row['epoch'] > last_time:
                last_time = row['epoch']

        print json.dumps(packet)
        
        day += one_day

    # Then dump updates as they happen
    while True:
        time.sleep(60)

        packet = {'type': 'keepalive',
                  'timestamp': int(time.time())}
        print json.dumps(packet)

        cursor.execute('select * from summary where username="%s" and '
                       'epoch > %d;'
                       %(username, last_time))
        for row in cursor:
            packet = {'type': 'update-user-summary',
                      'timestamp': int(time.time()),
                      'user': username,
                      'day': row['day'].strftime('%Y-%m-%d'),
                      'payload': row['data']}
            print json.dumps(packet)

            if row['epoch'] > last_time:
                last_time = row['epoch']
            
