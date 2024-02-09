#!/bin/bash
# helper script to restore the DB of a podman-compose env.
export PGDATABASE=wisdom
export PGHOST=localhost
export PGUSER=wisdom
export PGPASSWORD=wisdom

file=$1

if [ -z ${file} ]; then
    echo "Usage: ${0} target-file.sql"
    exit 1
fi

podman exec --user=root -it docker-compose_django_1 supervisorctl stop wisdom-processes:uwsgi
psql -h localhost -U wisdom postgres -c 'DROP DATABASE wisdom;'
psql -h localhost -U wisdom postgres -c 'CREATE DATABASE wisdom;'
pg_restore --dbname ${PGDATABASE} ${file}
podman exec --user=root -it docker-compose_django_1 supervisorctl start wisdom-processes:uwsgi
