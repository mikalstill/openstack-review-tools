#!/usr/bin/python

# Report on people doing triage work in a project. This was originally
# implemented so nova-core could track this in our weekly meetings.

import datetime
import re
import sys

import feedutils
import sql

from launchpadlib.launchpad import Launchpad

cachedir = '/tmp/launchpadlib-cache'


PERSON_RE = re.compile('.* \((.*)\)')


def ScrapeProject(projectname):
    launchpad = Launchpad.login_with('openstack-lp-scripts', 'production',
                                     cachedir, version='devel')
    proj = launchpad.projects[projectname]
    cursor = feedutils.GetCursor()

    now = datetime.datetime.now()
    since = datetime.datetime(now.year, now.month, now.day)
    since -= datetime.timedelta(days=365)

    bugs = proj.searchTasks(modified_since=since)
    for b in bugs:
        status_toucher = None
        importance_toucher = None
        triage_timestamp = None

        sys.stderr.write('\n%s\n' % b.title)
        sys.stderr.write('Reported by: %s\n' % b.bug.owner.display_name)
        cursor.execute('insert ignore into bugs (id, title, reporter, timestamp) '
                       'values(%s, %s, "%s", %s);'
                       %(b.bug.id, sql.FormatSqlValue('title', b.bug.title),
                         b.bug.owner.name,
                         sql.FormatSqlValue('timestamp', b.bug.date_created)))
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

                cursor.execute('insert ignore into bugevents '
                               '(id, component, timestamp, username, '
                               'field, pre, post) '
                               'values(%s, "%s", %s, "%s", "%s", "%s", "%s");'
                               %(b.bug.id, projectname, timestamp,
                                 activity.person.name,
                                 activity.whatchanged.split(': ')[1],
                                 oldvalue, newvalue))
                cursor.execute('commit;')

                # We define a triage as changing the status from New, and
                # changing the importance from Undecided. You must do both
                # to earn a cookie.
                if (activity.whatchanged.endswith(' status') and
                    (activity.oldvalue == 'New')):
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

            cursor.execute('insert ignore into bugtriage '
                           '(id, component, timestamp, username) '
                           'values(%s, "%s", %s, "%s");'
                           %(b.bug.id, projectname, timestamp,
                             status_toucher))



def ScrapeProjectWrapped(projectname):
    try:
        ScrapeProject(projectname)
    except:
        pass


ScrapeProjectWrapped('nova')
ScrapeProjectWrapped('openstack-common')
ScrapeProjectWrapped('oslo-incubator')
ScrapeProjectWrapped('glance')
ScrapeProjectWrapped('horizon')
ScrapeProjectWrapped('keystone')
ScrapeProjectWrapped('swift')
ScrapeProjectWrapped('cinder')

