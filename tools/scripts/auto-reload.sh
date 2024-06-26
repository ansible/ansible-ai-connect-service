#!/bin/env bash

if [ $# -lt 2 ]; then
    echo "Usage:"
    echo "    auto-reload.sh directory command"
    exit 1
fi

if [[ -n ${DJANGO_SETTINGS_MODULE} ]] && [[ ${DJANGO_SETTINGS_MODULE} == main.settings* ]]; then
    export DJANGO_SETTINGS_MODULE=ansible_ai_connect.${DJANGO_SETTINGS_MODULE}
fi

last_reload=$(date +%s)

inotifywait -mrq -e create,delete,attrib,close_write,move --exclude '(.*/tests/.*|.*/migrations/.*|.*/flycheck.*)' $1 | while read directory action file; do
   this_reload=$(date +%s)
   since_last=$((this_reload-last_reload))
   if [[ "$file" =~ ^[^.].*\.py$ ]] && [[ "$since_last" -gt 1 ]]; then
      echo "File changed: $file"
      echo "Running command: $2"
      eval $2
      last_reload=$(date +%s)
   fi
done
