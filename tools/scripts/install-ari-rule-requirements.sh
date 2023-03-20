#!/bin/bash
set -o errexit

rules_dir=/etc/ari/kb/rules

if [ -d $rules_dir ]; then
    for requirements in `find $rules_dir -name '*requirements.txt'`; do
        /var/www/venv/bin/python3 -m pip install --no-cache-dir -r $requirements
    done
fi
