#!/usr/bin/env bash

username=$1

if [ -z "${username}" ]; then
    echo "Usage ${0} my-username"
fi

podman --remote exec --user=root -it docker-compose_django_1 wisdom-manage createtoken --username ${username} --duration 6000000 --token-name my-dev-token
