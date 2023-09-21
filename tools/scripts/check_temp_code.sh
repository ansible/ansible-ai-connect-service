#!/bin/bash

files=$(git diff --cached --name-only --diff-filter=AM)

if [ -n "$files" ]; then
    if grep --exclude="check_temp_code.sh" -H TEMP_CODE $files; then
        echo "Blocking commit as TEMP_CODE was found."
        exit 1
    fi
fi
