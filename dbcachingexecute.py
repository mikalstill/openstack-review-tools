#!/usr/bin/python

import base64
import datetime
import subprocess
import time
import MySQLdb

import sql


def Execute(db, last_change, cmd_name, cmd, arg, cleanup=False):
  actual_cmd = cmd % arg
  print 'Executing: %s' % actual_cmd

  cursor = db.cursor(MySQLdb.cursors.DictCursor)
  try:
    cursor.execute('create table commands_%s (arg varchar(500), '
                   'timestamp datetime, epoch int, result longtext, '
                   'primary key(arg, timestamp), index(timestamp), '
                   'index(epoch)) '
                   'engine=innodb;' % cmd_name)
  except:
    pass

  cursor.execute('select timestamp, epoch, result from commands_%s '
                 'where arg="%s" order by timestamp desc limit 1;'
                 %(cmd_name, arg))
  if cursor.rowcount > 0:
    row = cursor.fetchone()
    if row['epoch'] > last_change:
      print ' ... Using cached result'
      return base64.decodestring(row['result']).split('\n')

  p = subprocess.Popen(actual_cmd,
                       shell=True,
                       stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE)
  out = p.stdout.read()
  print ' ... Got %d bytes' % len(out)

  cursor.execute('insert into commands_%s (arg, timestamp, epoch, result) '
                 'values ("%s", now(), %d, "%s");'
                 %(cmd_name, arg, int(time.time()), base64.encodestring(out)))
  cursor.execute('commit;')

  if cleanup:
    too_old = datetime.datetime.now()
    too_old -= datetime.timedelta(days=14)

    cursor.execute('delete from commands_%s where timestamp < %s;'
                   %(cmd_name, sql.FormatSqlValue('timestamp', too_old)))
    cursor.execute('commit;')

  return out.split('\n')
