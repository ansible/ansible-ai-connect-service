#!/bin/bash
set -o errexit

/usr/bin/python3 -m venv /var/www/venv
/var/www/venv/bin/python3 -m pip --no-cache-dir install pip-tools

TARGET=$(uname -m)
/var/www/venv/bin/pip-compile -o requirements-${TARGET}.txt requirements.in
/var/www/venv/bin/pip-compile -o requirements-dev-${TARGET}.txt requirements-dev.in
