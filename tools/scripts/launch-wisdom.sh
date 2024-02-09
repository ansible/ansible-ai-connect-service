#!/bin/bash
set -o errexit

if [[ -n ${DJANGO_SETTINGS_MODULE} ]] && [[ ${DJANGO_SETTINGS_MODULE} == main.settings* ]]; then
    export DJANGO_SETTINGS_MODULE=ansible_wisdom.${DJANGO_SETTINGS_MODULE}
fi

database_ready() {
/var/www/venv/bin/python <<EOF
import sys
from django.db import connection

try:
    connection.ensure_connection()
except Exception:
    sys.exit(1)
EOF
}

until database_ready
do
    echo "Waiting until the database is ready..."
    sleep 5
done

/var/www/venv/bin/wisdom-manage migrate --noinput
/var/www/venv/bin/wisdom-manage createcachetable
if [ "${DEPLOYMENT_MODE}" == "upstream" ]; then
    # for upstream, creating a out-of-box tesing user for starting quick
    echo "Creating a testing user for upstream mode..."
    /var/www/venv/bin/python ansible_wisdom/manage.py createtoken --username testuser --password testuser --token-name testuser_token --create-user
fi
/var/www/venv/bin/wisdom-manage collectstatic --noinput

/usr/local/bin/supervisord -n
