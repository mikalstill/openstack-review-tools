#!/usr/bin/python

# Take gerrit status feeds and turn them into an RSS feed

import datetime
import json
import sys
import time
import MySQLdb

import sql

def SendPacket(packet):
    packet['timestamp'] = int(time.time())
    print json.dumps(packet)
    sys.stdout.flush()


if __name__ == '__main__':
    # Read config from a file
    with open('/srv/config/summaryfeed') as f:
        flags = json.loads(f.read())

    print 'Content-Type: text/plain\r'
    print '\r'
    sys.stdout.flush()

    db = MySQLdb.connect(user = flags['dbuser'],
                         db = flags['dbname'],
                         passwd = flags['dbpassword'])
    cursor = db.cursor(MySQLdb.cursors.DictCursor)

    # Fetch the last seven days of results to start off with
    day = datetime.datetime.now()
    one_day = datetime.timedelta(days=1)
    last_time = 0

    username = 'mikalstill'

    day -= one_day * 6
    for i in range(7):
        timestamp = sql.FormatSqlValue('timestamp', day)
        cursor.execute('select * from summary where username="%s" and '
                       'day=date(%s);'
                       %(username, timestamp))
        packet = {'type': 'initial-user-summary',
                  'user': username,
                  'day': day.isoformat()}
        if cursor.rowcount > 0:
            row = cursor.fetchone()
            packet['payload'] = json.loads(row['data'])
            packet['written-at'] = row['epoch']

            if row['epoch'] > last_time:
                last_time = row['epoch']
        else:
            packet['payload'] = {'__total__': 0}

        SendPacket(packet)
        day += one_day

    # Then dump updates as they happen
    while True:
        time.sleep(60)

        # Rebuild the DB connection in case the DB went away
        db = MySQLdb.connect(user = flags['dbuser'],
                             db = flags['dbname'],
                             passwd = flags['dbpassword'])
        cursor = db.cursor(MySQLdb.cursors.DictCursor)

        # Now check for updates
        SendPacket({'type': 'keepalive'})
        SendPacket({'type': 'debug',
                    'payload': 'Querying for updates after %d' % last_time})

        cursor.execute('select * from summary where username="%s" and '
                       'epoch > %d;'
                       %(username, last_time))

        SendPacket({'type': 'debug',
                    'payload': 'Found %d updates' % cursor.rowcount})

        for row in cursor:
            SendPacket({'type': 'update-user-summary',
                        'user': username,
                        'written-at': row['epoch'],
                        'day': row['day'].isoformat(),
                        'payload': row['data']})

            if row['epoch'] > last_time:
                last_time = row['epoch']
            
