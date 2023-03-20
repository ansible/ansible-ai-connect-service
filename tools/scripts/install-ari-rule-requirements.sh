#!/bin/bash
set -o errexit

if [ ! -z $ARI_KB_PATH ]; then
    rules_dir="$ARI_KB_PATH/rules"
    if [ -d $rules_dir ]; then
        for requirements in `find $rules_dir -name '*requirements.txt'`; do
            /var/www/venv/bin/python3 -m pip install --no-cache-dir -r $requirements
        done
    fi
fi