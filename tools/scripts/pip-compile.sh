#!/bin/bash
set -o errexit

dnf install -y python3.11
dnf -y install git

/usr/bin/python3.11 -m venv /var/www/venv
/var/www/venv/bin/python3.11 -m pip --no-cache-dir install pip-tools

TARGET=$(uname -m)
/var/www/venv/bin/pip-compile -o requirements-${TARGET}.txt requirements.in
/var/www/venv/bin/pip-compile -o requirements-dev-${TARGET}.txt requirements-dev.in
