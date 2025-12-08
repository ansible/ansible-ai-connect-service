#!/bin/bash
set -o errexit

dnf install -y python3.12-devel gcc
dnf -y install git

/usr/bin/python3.12 -m venv /var/www/venv
/var/www/venv/bin/python3.12 -m pip --no-cache-dir install pip-tools

TARGET=$(uname -m)
/var/www/venv/bin/pip-compile -o requirements-${TARGET}.txt requirements.in
/var/www/venv/bin/pip-compile -o requirements-dev-${TARGET}.txt -c requirements-${TARGET}.txt requirements-dev.in
