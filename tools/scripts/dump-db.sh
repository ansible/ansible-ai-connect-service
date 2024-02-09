#!/bin/bash
# helper script to dump the DB of a podman-compose env.
export PGDATABASE=wisdom
export PGHOST=localhost
export PGUSER=wisdom
export PGPASSWORD=wisdom

file=$1

if [ -z ${file} ]; then
    echo "Usage: ${0} target-file.sql"
    exit 1
fi

pg_dump -Fc --create --file=${file}
