#!/bin/bash
/var/www/venv/bin/python ansible_wisdom/manage.py migrate --noinput

cd ansible_wisdom/
/usr/local/bin/supervisord -n
