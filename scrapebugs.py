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


def ScrapeProject(projectname, days):
    launchpad = Launchpad.login_with('openstack-lp-scripts', 'production',
                                     CACHEDIR, version='devel')
    proj = launchpad.projects[projectname]
    cursor = feedutils.GetCursor()

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
            cursor.execute('insert ignore into bugs '
                           '(id, title, reporter, timestamp) '
                           'values(%s, %s, "%s", %s);'
                           %(b.bug.id,
                             sql.FormatSqlValue('title', b.bug.title),
                             b.bug.owner.name,
                             sql.FormatSqlValue('timestamp',
                                                b.bug.date_created)))
            cursor.execute('commit;')

        for bugtask in b.bug.bug_tasks:
            sys.stderr.write('  Targetted to %s on %s by %s\n'
                             %(bugtask.bug_target_name, bugtask.date_created,
                               bugtask.owner.name))

            if WRITE:
                timestamp = sql.FormatSqlValue('timestamp',
                                               bugtask.date_created)
                cursor.execute('insert ignore into bugevents '
                               '(id, component, timestamp, username, '
                               'field, pre, post) '
                               'values(%s, "%s", %s, "%s", "targetted", NULL, '
                               '"%s");'
                               %(b.bug.id, bugtask.bug_target_name, timestamp,
                                 bugtask.owner.name, bugtask.bug_target_name))
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
                    cursor.execute('insert ignore into bugevents '
                                   '(id, component, timestamp, username, '
                                   'field, pre, post) '
                                   'values(%s, "%s", %s, "%s", "%s", "%s", '
                                   '"%s");'
                                   %(b.bug.id, projectname, timestamp,
                                     activity.person.name,
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

        if (status_toucher and importance_toucher and
            (status_toucher == importance_toucher)):
            sys.stderr.write('  *** %s triaged this ticket **\n'
                             % status_toucher)
            timestamp = sql.FormatSqlValue('timestamp', triage_timestamp)

            if WRITE:
                cursor.execute('insert ignore into bugtriage '
                               '(id, component, timestamp, username) '
                               'values(%s, "%s", %s, "%s");'
                               %(b.bug.id, projectname, timestamp,
                                 status_toucher))
                if cursor.rowcount > 0:
                    # This is a new review, we assume we're the only writer
                    print 'New triage from %s' % status_toucher
                    cursor.execute('select * from bugtriagesummary where '
                                   'username="%s" and day=date(%s);'
                                   %(status_toucher, timestamp))
                    if cursor.rowcount > 0:
                        row = cursor.fetchone()
                        summary = json.loads(row['data'])
                    else:
                        summary = {}

                    summary.setdefault(projectname, 0)
                    summary.setdefault('__total__', 0)
                    summary[projectname] += 1
                    summary['__total__'] += 1

                    cursor.execute('delete from bugtriagesummary where '
                                   'username="%s" and day=date(%s);'
                                   %(status_toucher, timestamp))
                    cursor.execute('insert into bugtriagesummary'
                                   '(day, username, data, epoch) '
                                   'values (date(%s), "%s", \'%s\', %d);'
                                   %(timestamp, status_toucher,
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
cursor.execute('select count(*) from bugevents;')
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
ScrapeProjectWrapped('keystone, days')
ScrapeProjectWrapped('swift', days)
ScrapeProjectWrapped('cinder', days)

