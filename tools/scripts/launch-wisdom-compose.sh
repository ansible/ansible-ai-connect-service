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
/var/www/venv/bin/wisdom-manage collectstatic --noinput
/var/www/venv/bin/wisdom-manage createapplication --name "Ansible Lightspeed for VS Code" --client-id Vu2gClkeR5qUJTUGHoFAePmBznd6RZjDdy5FW2wy --redirect-uris "vscode://redhat.ansible vscodium://redhat.ansible vscode-insiders://redhat.ansible code-oss://redhat.ansible checode://redhat.ansible" public authorization-code

/usr/local/bin/supervisord -n
