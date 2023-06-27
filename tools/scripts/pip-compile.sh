#!/bin/bash
set -o errexit

cd /var/www/wisdom
/usr/bin/python3 -m venv /var/www/venv
/var/www/venv/bin/python3 -m pip --no-cache-dir install pip-tools

/var/www/venv/bin/pip-compile requirements.in
/var/www/venv/bin/pip-compile requirements-dev.in
