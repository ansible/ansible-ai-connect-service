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
    /var/www/venv/bin/wisdom-manage createtoken --username testuser --password testuser --token-name testuser_token --create-user
	/var/www/venv/bin/wisdom-manage createsuperuser --noinput --username admin --email admin@example.com
fi
if [ ! "${DEPLOYMENT_MODE}" == "saas" ]; then
    /var/www/venv/bin/wisdom-manage createapplication --name "${ANSIBLE_AI_PROJECT_NAME:-Ansible AI Connect} for VS Code" --client-id Vu2gClkeR5qUJTUGHoFAePmBznd6RZjDdy5FW2wy --redirect-uris "vscode://redhat.ansible vscodium://redhat.ansible vscode-insiders://redhat.ansible code-oss://redhat.ansible checode://redhat.ansible" public authorization-code
fi
/var/www/venv/bin/wisdom-manage collectstatic --noinput

/usr/local/bin/supervisord -n
