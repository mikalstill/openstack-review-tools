#!/usr/bin/python

# Report on people doing triage work in a project. This was originally
# implemented so nova-core could track this in our weekly meetings.

import datetime
import sys

from launchpadlib.launchpad import Launchpad

cachedir = '/tmp/launchpadlib-cache'


def ScrapeProject(projectname):
    sys.stderr.write('Logging in...\n')

    launchpad = Launchpad.login_with('openstack-lp-scripts', 'production',
                                     cachedir, version='devel')

    sys.stderr.write('Retrieving project...\n')
    proj = launchpad.projects[projectname]

    sys.stderr.write('Considering bugs changed in the last two weeks...\n')
    now = datetime.datetime.now()
    since = datetime.datetime(now.year, now.month, now.day)
    since -= datetime.timedelta(days=14)

    bugs = proj.searchTasks(modified_since=since)
    for b in bugs:
        status_toucher = None
        importance_toucher = None

        sys.stderr.write('\n%s\n' % b.title)
        sys.stderr.write('Reported by: %s\n' % b.bug.owner.display_name)
        for activity in b.bug.activity:
            if activity.whatchanged.startswith('%s: ' % projectname):
                sys.stderr.write('  %s :: %s -> %s :: %s on %s\n'
                                 % (activity.whatchanged,
                                    activity.oldvalue,
                                    activity.newvalue,
                                    activity.person.display_name,
                                    activity.datechanged))

                if activity.datechanged > since:
                    # We define a triage as changing the status from New, and
                    # changing the importance from Undecided. You must do both
                    # to earn a cookie.
                    if (activity.whatchanged.endswith(' status') and
                        (activity.oldvalue == 'New')):
                        status_toucher = activity.person.display_name

                    if (activity.whatchanged.endswith(' importance') and
                        (activity.oldvalue == 'Undecided')):
                        importance_toucher = activity.person.display_name

        if (status_toucher and importance_toucher and
            (status_toucher == importance_toucher)):
            sys.stderr.write('  *** %s triaged this ticket **\n'
                             % status_toucher)


ScrapeProject('nova')
