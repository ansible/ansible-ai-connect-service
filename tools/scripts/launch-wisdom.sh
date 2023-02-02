#!/bin/bash
until echo -e 'import sys\nfrom django.db import connection\ntry:\n    connection.ensure_connection()\nexcept Exception:\n    sys.exit(1)\n' | /var/www/venv/bin/python ansible_wisdom/manage.py shell
do
    echo "Waiting until the database is ready..."
    sleep 5
done

/var/www/venv/bin/python ansible_wisdom/manage.py migrate --noinput

cd ansible_wisdom/
/usr/local/bin/supervisord -n
