#!/usr/bin/python


import re

import feedutils


user_re = re.compile('^.*username:([^ ]+) +\| (.+)$')

groups = {}
with open('groups.txt') as f:
    for l in f.readlines():
        m = user_re.match(l)
        if m:
            groups.setdefault(m.group(2), [])
            groups[m.group(2)].append(m.group(1))

cursor = feedutils.GetCursor()
for group in groups:
    print '%s: %s' %(group, ', '.join(groups[group]))
    cursor.execute('delete from groups where name="%s";' % group)
    cursor.execute('insert into groups(name, members) values ("%s", "%s");'
                   %(group, ' '.join(groups[group])))
    cursor.execute('commit;')
