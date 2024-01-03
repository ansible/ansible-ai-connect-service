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
/var/www/venv/bin/python ansible_wisdom/manage.py collectstatic --noinput
/var/www/venv/bin/python ansible_wisdom/manage.py createapplication --name "Ansible Lightspeed for VS Code" --client-id Vu2gClkeR5qUJTUGHoFAePmBznd6RZjDdy5FW2wy --redirect-uris "vscode://redhat.ansible vscodium://redhat.ansible vscode-insiders://redhat.ansible code-oss://redhat.ansible checode://redhat.ansible" public authorization-code

cd ansible_wisdom/
/usr/local/bin/supervisord -n
