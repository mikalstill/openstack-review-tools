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
ONLY = []
FORCEDAYS = None


def UpdateTrackingTables(eventname, b, projectname, timestamp, user):
    subcursor.execute('insert ignore into bug%s%s '
                      '(id, component, timestamp, '
                      'username) '
                      'values(%s, "%s", %s, "%s");'
                      %(eventname, VERSION, b.bug.id, projectname, timestamp,
                        user))
    if subcursor.rowcount > 0:
        print '  New close for %s' % user
        cursor.execute('select * from '
                       'bug%ssummary%s where '
                       'username="%s" and day=date(%s);'
                       %(eventname, VERSION, user, timestamp))
        if cursor.rowcount > 0:
            row = cursor.fetchone()
            summary = json.loads(row['data'])
        else:
            summary = {}

        summary.setdefault(projectname, 0)
        summary.setdefault('__total__', 0)
        summary[projectname] += 1
        summary['__total__'] += 1

        cursor.execute('delete from bug%ssummary%s '
                       'where username="%s" and '
                       'day=date(%s);'
                       %(eventname, VERSION, user, timestamp))
        cursor.execute('insert into bug%ssummary%s'
                       '(day, username, data, epoch) '
                       'values (date(%s), "%s", '
                       '\'%s\', %d);'
                       %(eventname, VERSION, timestamp, user,
                         json.dumps(summary), int(time.time())))


def ScrapeProject(projectname, days):
    launchpad = Launchpad.login_with('openstack-lp-scripts', 'production',
                                     CACHEDIR)
    proj = launchpad.projects[projectname]
    cursor = feedutils.GetCursor()
    subcursor = feedutils.GetCursor()

    now = datetime.datetime.now()
    since = datetime.datetime(now.year, now.month, now.day)
    since -= datetime.timedelta(days=days)

    bugs = proj.searchTasks(modified_since=since,
                            status=["New",
                                    "Incomplete",
                                    "Invalid",
                                    "Won't Fix",
                                    "Confirmed",
                                    "Triaged",
                                    "In Progress",
                                    "Fix Committed",
                                    "Fix Released"])
    for b in bugs:
        if ONLY and b.bug.id not in ONLY:
            continue

        status_toucher = None
        importance_toucher = None
        triage_timestamp = None

        print '\n%s' % b.title
        print 'Reported by: %s' % b.bug.owner.name
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

            for dup in getattr(b.bug, 'duplicates', []):
                print 'Duplicate: %s' % dup.id
                cursor.execute('update bugs%s set duplicateof=%s where id=%s;'
                               %(VERSION, b.bug.id, dup.id))
                cursor.execute('commit;')

        for bugtask in b.bug.bug_tasks:
            print ('  Targetted to %s on %s by %s'
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
                cursor.execute('insert ignore into bugevents%s '
                               '(id, component, timestamp, username, '
                               'field, pre, post) '
                               'values(%s, "%s", %s, "%s", "importance", "-", '
                               '"%s");'
                               %(VERSION, b.bug.id, bugtask.bug_target_name,
                                 timestamp, bugtask.owner.name,
                                 bugtask.importance))
                cursor.execute('insert ignore into bugevents%s '
                               '(id, component, timestamp, username, '
                               'field, pre, post) '
                               'values(%s, "%s", %s, "%s", "status", "-", '
                               '"%s");'
                               %(VERSION, b.bug.id, bugtask.bug_target_name,
                                 timestamp, bugtask.owner.name,
                                 bugtask.status))
                cursor.execute('commit;')

            if bugtask.assignee:
                time_diff = bugtask.date_assigned - bugtask.date_created
                if time_diff.seconds < 60:
                    print ('  *** special case: bug assigned to %s on task '
                           'creation ***'
                           % bugtask.assignee)
                    if WRITE:
                        timestamp = sql.FormatSqlValue('timestamp',
                                                       bugtask.date_assigned)
                        cursor.execute('insert ignore into bugevents%s '
                                       '(id, component, timestamp, username, '
                                       'field, pre, post) '
                                       'values(%s, "%s", %s, "%s", "assignee", "-", '
                                       '"%s");'
                                       %(VERSION, b.bug.id, bugtask.bug_target_name,
                                         timestamp, bugtask.owner.name,
                                         bugtask.assignee.name))
                        cursor.execute('commit;')

        for activity in b.bug.activity:
            if activity.whatchanged.startswith('%s: ' % projectname):
                timestamp = sql.FormatSqlValue('timestamp',
                                               activity.datechanged)
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

                print('  %s :: %s -> %s :: %s on %s'
                      % (activity.whatchanged,
                         oldvalue,
                         newvalue,
                         activity.person.name,
                         activity.datechanged))

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

                # Code review sent for a bug
                if(activity.whatchanged.endswith(' status') and
                   (activity.newvalue in ['In Progress'])):
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
                            UpdateTrackingTables('progress', projectname,
                                                 timestamp, user)
                            subcursor.execute('commit;')

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

                            UpdateTrackingTables('close', projectname,
                                                 timestamp, user)
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
            print '  *** %s triaged this bug ***' % status_toucher
            timestamp = sql.FormatSqlValue('timestamp', triage_timestamp)

            if WRITE:
                UpdateTrackingTables('triage', projectname, timestamp, user)
                cursor.execute('commit;')


def ScrapeProjectWrapped(projectname, days):
    for release in ['', '/austin', '/bexar', '/cactus', '/diablo',
                    '/essex', '/folsom', '/grizzly', '/havana']:
        try:
            ScrapeProject(projectname + release, days)
        except Exception, e:
            print '*******************'
            print '%s%s errored with: %s' %(projectname, release, e)
            print '*******************'


# If we have no data, grab a lot!
if FORCEDAYS:
    days = FORCEDAYS
else:
    cursor = feedutils.GetCursor()
    cursor.execute('select count(*) from bugevents%s;' % VERSION)
    if cursor.fetchone()['count(*)'] > 0:
        days = 2
    else:
        days = 1000
print 'Fetching %d days of bugs' % days

ScrapeProjectWrapped('nova', days)
ScrapeProjectWrapped('openstack-common', days)
ScrapeProjectWrapped('oslo', days)
ScrapeProjectWrapped('glance', days)
ScrapeProjectWrapped('horizon', days)
ScrapeProjectWrapped('keystone', days)
ScrapeProjectWrapped('swift', days)
ScrapeProjectWrapped('cinder', days)

