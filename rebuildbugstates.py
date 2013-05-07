#!/usr/bin/python

# Rebuild the bug states table.

import datetime
import sys
import MySQLdb

import feedutils
import sql


STATES = {}
DUPLICATES = {}
CLOSED_STATES = ('Fix Committed','Fix Released', 'Opinion', 'Won\'t Fix', 'Invalid', 'Expired')


def FindDuplicates():
    global DUPLICATES

    cursor = feedutils.GetCursor()
    cursor.execute('select * from bugs where duplicateof is not null;')
    for row in cursor:
        DUPLICATES[row['id']] = row['duplicateof']


def RebuildStates():
    global DUPLICATES

    cursor = feedutils.GetCursor()

    cursor.execute('select distinct(id) from bugevents;')
    bugids = []
    for row in cursor:
        bugids.append(row['id'])

    cursor.execute('select distinct(component) from bugevents;')
    components = []
    for row in cursor:
        components.append(row['component'])    

    for id in bugids:
        if id in DUPLICATES:
            continue

        for component in components:
            opened = None
            importance = 'Undecided'
            status = 'Unknown'

            cursor.execute('select * from bugevents where '
                           'id=%s and component="%s";'
                           %(id, component))
            for row in cursor:
                # Opened, reopened
                if row['field'] == 'targetted':
                    if not status in CLOSED_STATES:
                        opened = row['timestamp']
                elif row['field'] == 'status' and row['pre'] in CLOSED_STATES and not row['post'] in CLOSED_STATES:
                    opened = row['timestamp']

                # Closed
                elif row['field'] == 'status' and row['post'] in CLOSED_STATES:
                    EmitState(id, component, importance, opened, row['timestamp'])
                    opened = None
                    status = row['post']
                elif row['field'] == 'status':
                   status = row['post']

                # Changed importance
                elif row['field'] == 'importance':
                    if not status in CLOSED_STATES:
                        EmitState(id, component, importance, opened, row['timestamp'])
                        opened = row['timestamp']
                    importance = row['post']

                # Don't care
                elif row['field'] == 'assignee':
                    pass
                elif row['field'] == 'milestone':
                    pass

                # Unknown row!
                else:
                    print row

            if opened:
                EmitState(id, component, importance, opened, datetime.datetime.now())


def EmitState(id, component, importance, start, end):
    global STATES

    if not start:
        return

    day = datetime.datetime(start.year, start.month, start.day)
    while day < end:
        STATES.setdefault(component, {})
        STATES[component].setdefault(importance, {})
        STATES[component][importance].setdefault(day, [])
        STATES[component][importance][day].append(str(id))

        STATES[component].setdefault('__total__', {})
        STATES[component]['__total__'].setdefault(day, [])
        STATES[component]['__total__'][day].append(str(id))

        day += datetime.timedelta(days=1)


if __name__ == '__main__':
    FindDuplicates()
    RebuildStates()

    cursor = feedutils.GetCursor()
    cursor.execute('delete from bugcounts;')
    for component in STATES:
        for importance in STATES[component]:
            for day in STATES[component][importance]:
                timestamp = sql.FormatSqlValue('timestamp', day)
                STATES[component][importance][day].sort()
                cursor.execute('insert ignore into bugcounts '
                               '(component, importance, day, count, ids) values '
                               '("%s", "%s", %s, %d, "%s");'
                               %(component, importance, timestamp,
                                 len(STATES[component][importance][day]),
                                 ' '.join(STATES[component][importance][day])))
    cursor.execute('commit;')
