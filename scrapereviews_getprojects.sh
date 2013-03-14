#!/bin/bash

for item in `wget -O - "https://raw.github.com/openstack-infra/config/master/modules/openstack_project/templates/review.projects.yaml.erb" 2> /dev/null | egrep "^- project" | grep "openstack" | sed 's/- project: //'`
do
  echo "    Reviews('$item')"
done
