#!/usr/bin/python

# Report on people doing triage work in a project. This was originally
# implemented so nova-core could track this in our weekly meetings.

import datetime
import json
import re
import sys
import time

import feedutils
import sql

from launchpadlib.launchpad import Launchpad

CACHEDIR = '/tmp/launchpadlib-cache'
PERSON_RE = re.compile('.* \((.*)\)')
WRITE = True
VERSION = ''


def ScrapeProject(projectname, days):
    launchpad = Launchpad.login_with('openstack-lp-scripts', 'production',
                                     CACHEDIR, version='devel')
    proj = launchpad.projects[projectname]
    cursor = feedutils.GetCursor()
    subcursor = feedutils.GetCursor()

    now = datetime.datetime.now()
    since = datetime.datetime(now.year, now.month, now.day)
    since -= datetime.timedelta(days=days)

    bugs = proj.searchTasks(modified_since=since)
    for b in bugs:
        status_toucher = None
        importance_toucher = None
        triage_timestamp = None

        sys.stderr.write('\n%s\n' % b.title)
        sys.stderr.write('Reported by: %s\n' % b.bug.owner.display_name)
        if WRITE:
            cursor.execute('insert ignore into bugs%s '
                           '(id, title, reporter, timestamp, component) '
                           'values(%s, %s, "%s", %s, "%s");'
                           %(VERSION, b.bug.id,
                             sql.FormatSqlValue('title', b.bug.title),
                             b.bug.owner.name,
                             sql.FormatSqlValue('timestamp',
                                                b.bug.date_created),
                             projectname))
            cursor.execute('commit;')

        for bugtask in b.bug.bug_tasks:
            sys.stderr.write('  Targetted to %s on %s by %s\n'
                             %(bugtask.bug_target_name, bugtask.date_created,
                               bugtask.owner.name))

            if WRITE:
                timestamp = sql.FormatSqlValue('timestamp',
                                               bugtask.date_created)
                cursor.execute('insert ignore into bugevents%s '
                               '(id, component, timestamp, username, '
                               'field, pre, post) '
                               'values(%s, "%s", %s, "%s", "targetted", NULL, '
                               '"%s");'
                               %(VERSION, b.bug.id, bugtask.bug_target_name,
                                 timestamp, bugtask.owner.name,
                                 bugtask.bug_target_name))
                cursor.execute('commit;')

        for activity in b.bug.activity:
            if activity.whatchanged.startswith('%s: ' % projectname):
                timestamp = sql.FormatSqlValue('timestamp',
                                               activity.datechanged)
                sys.stderr.write('  %s :: %s -> %s :: %s on %s\n'
                                 % (activity.whatchanged,
                                    activity.oldvalue,
                                    activity.newvalue,
                                    activity.person.display_name,
                                    activity.datechanged))

                oldvalue = activity.oldvalue
                newvalue = activity.newvalue

                try:
                    m = PERSON_RE.match(oldvalue)
                    if m:
                        oldvalue = m.group(1)
                except:
                    pass

                try:
                    m = PERSON_RE.match(newvalue)
                    if m:
                        newvalue = m.group(1)
                except:
                    pass

                if WRITE:
                    cursor.execute('insert ignore into bugevents%s '
                                   '(id, component, timestamp, username, '
                                   'field, pre, post) '
                                   'values(%s, "%s", %s, "%s", "%s", "%s", '
                                   '"%s");'
                                   %(VERSION, b.bug.id, projectname,
                                     timestamp, activity.person.name,
                                     activity.whatchanged.split(': ')[1],
                                     oldvalue, newvalue))
                    cursor.execute('commit;')

                # We define a triage as changing the status from New, and
                # changing the importance from Undecided. You must do both
                # to earn a cookie.
                if (activity.whatchanged.endswith(' status') and
                    (activity.oldvalue in ['New', 'Incomplete']) and
                    (activity.newvalue in ['Confirmed', 'Triaged'])):
                    status_toucher = activity.person.name
                    if (not triage_timestamp or
                        activity.datechanged > triage_timestamp):
                       triage_timestamp = activity.datechanged
                    
                if (activity.whatchanged.endswith(' importance') and
                    (activity.oldvalue == 'Undecided')):
                    importance_toucher = activity.person.name
                    if (not triage_timestamp or
                        activity.datechanged > triage_timestamp):
                       triage_timestamp = activity.datechanged

                # Marking a bug as invalid is a special super cookie!
                if (activity.whatchanged.endswith(' status') and
                    (activity.newvalue in ['Invalid', 'Opinion'])):
                    status_toucher = activity.person.name
                    importance_toucher = activity.person.name
                    triage_timestamp = activity.datechanged

                # A bug was marked as fixed
                if(activity.whatchanged.endswith(' status') and
                   (activity.newvalue in ['Fix Committed'])):
                    # Find out who the bug was assigned to
                    cursor.execute('select * from bugevents%s where '
                                   'id=%s and component="%s" and '
                                   'field="assignee" and '
                                   'timestamp < %s '
                                   'order by timestamp desc limit 1;'
                                   %(VERSION, b.bug.id, projectname,
                                     timestamp))

                    for row in cursor:
                        user = row['post']
                        if WRITE:
                            subcursor.execute('update bugs%s set '
                                              'closedby="%s" where id=%s '
                                              'and component="%s";'
                                              %(VERSION, user, b.bug.id,
                                                projectname))
                            subcursor.execute('commit;')
                            print '  *** %s closed this bug ***' % user

                            subcursor.execute('insert ignore into bugclose%s '
                                              '(id, component, timestamp, '
                                              'username) '
                                              'values(%s, "%s", %s, "%s");'
                                              %(VERSION, b.bug.id, projectname,
                                                timestamp, user))
                            if subcursor.rowcount > 0:
                                print '  New close for %s' % user

                                cursor.execute('select * from '
                                               'bugclosesummary%s where '
                                               'username="%s" and day=date(%s);'
                                               %(VERSION, user,
                                                 timestamp))
                                if cursor.rowcount > 0:
                                    row = cursor.fetchone()
                                    summary = json.loads(row['data'])
                                else:
                                    summary = {}

                                summary.setdefault(projectname, 0)
                                summary.setdefault('__total__', 0)
                                summary[projectname] += 1
                                summary['__total__'] += 1

                                cursor.execute('delete from bugclosesummary%s '
                                               'where username="%s" and '
                                               'day=date(%s);'
                                               %(VERSION, user,
                                                 timestamp))
                                cursor.execute('insert into bugclosesummary%s'
                                               '(day, username, data, epoch) '
                                               'values (date(%s), "%s", '
                                               '\'%s\', %d);'
                                               %(VERSION, timestamp, user,
                                                 json.dumps(summary),
                                                 int(time.time())))

                                subcursor.execute('commit;')

                # A bug was unfixed
                if(activity.whatchanged.endswith(' status') and
                   (activity.oldvalue in ['Fix Committed']) and
                   (not activity.newvalue in ['Fix Released'])):
                    if WRITE:
                        cursor.execute('update bugs%s set closedby = null '
                                       'where id=%s and component="%s";'
                                       %(VERSION, b.bug.id, projectname))
                        cursor.execute('commit;')
                    print '  *** This bug was unclosed ***'

        if (status_toucher and importance_toucher and
            (status_toucher == importance_toucher)):
            sys.stderr.write('  *** %s triaged this bug ***\n'
                             % status_toucher)
            timestamp = sql.FormatSqlValue('timestamp', triage_timestamp)

            if WRITE:
                cursor.execute('insert ignore into bugtriage%s '
                               '(id, component, timestamp, username) '
                               'values(%s, "%s", %s, "%s");'
                               %(VERSION, b.bug.id, projectname, timestamp,
                                 status_toucher))
                if cursor.rowcount > 0:
                    # This is a new review, we assume we're the only writer
                    print '  New triage from %s' % status_toucher
                    cursor.execute('select * from bugtriagesummary%s where '
                                   'username="%s" and day=date(%s);'
                                   %(VERSION, status_toucher, timestamp))
                    if cursor.rowcount > 0:
                        row = cursor.fetchone()
                        summary = json.loads(row['data'])
                    else:
                        summary = {}

                    summary.setdefault(projectname, 0)
                    summary.setdefault('__total__', 0)
                    summary[projectname] += 1
                    summary['__total__'] += 1

                    cursor.execute('delete from bugtriagesummary%s where '
                                   'username="%s" and day=date(%s);'
                                   %(VERSION, status_toucher, timestamp))
                    cursor.execute('insert into bugtriagesummary%s'
                                   '(day, username, data, epoch) '
                                   'values (date(%s), "%s", \'%s\', %d);'
                                   %(VERSION, timestamp, status_toucher,
                                     json.dumps(summary),
                                     int(time.time())))

                cursor.execute('commit;')


def ScrapeProjectWrapped(projectname, days):
    try:
        ScrapeProject(projectname, days)
    except Exception, e:
        print e
        print '*******************'


# If we have no data, grab a lot!
cursor = feedutils.GetCursor()
cursor.execute('select count(*) from bugevents%s;' % VERSION)
if cursor.fetchone()['count(*)'] > 0:
    days = 2
else:
    days = 1000
print 'Fetching %d days of bugs' % days

ScrapeProjectWrapped('nova', days)
ScrapeProjectWrapped('openstack-common', days)
ScrapeProjectWrapped('oslo-incubator', days)
ScrapeProjectWrapped('glance', days)
ScrapeProjectWrapped('horizon', days)
ScrapeProjectWrapped('keystone', days)
ScrapeProjectWrapped('swift', days)
ScrapeProjectWrapped('cinder', days)

