#!/bin/bash
set -o errexit

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

/var/www/venv/bin/python ansible_wisdom/manage.py migrate --noinput
/var/www/venv/bin/python ansible_wisdom/manage.py createcachetable
if [ "${DEPLOYMENT_MODE}" == "upstream" ]; then
    # for upstream, creating a out-of-box tesing user for starting quick
    echo "Creating a testing user for upstream mode..."
    /var/www/venv/bin/python ansible_wisdom/manage.py createtoken --username testuser --password testuser --token-name testuser_token --create-user
fi
/var/www/venv/bin/python ansible_wisdom/manage.py collectstatic --noinput

cd ansible_wisdom/
/usr/local/bin/supervisord -n
