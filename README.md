# Ansible Wisdom service

Note: This repository is under active development and is not yet ready for production use.

## Running the server locally

1. Clone the repository, create a virtual environment and install all the dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

### Install model server dependencies
:information_source: NOTE: Be sure to follow any post-installation steps suggested by the OpenJDK installer

```bash
brew install openjdk
```

1. Copy the model to the `MODEL_PATH` folder

1. Build the model archive

```bash
export MODEL_PATH=./model/wisdom
make model-archive
```

1. Run the server

### Non-container
```bash
make run-model-server
```

### Container
```bash
make container
make run-model-server-container
```

:information_source: NOTE: to include the model archive in the container image (for running via podman-remote or on macOS)
```bash
export MODEL_PATH=./model/wisdom
export ENVIRONMENT=production
make model-archive
make container
make run-model-server-container
```

## Running the server on OpenShift

1. Generate model archive
```bash
make model-archive
```
1. Create new project
```bash
oc new-project <project name>
```

1. Assign privileged context to builder account (:warning: do not do this in production)
```bash
oc adm policy add-scc-to-user privileged system:serviceaccount:<project name>:builder
```

1. Build/deploy container and expose route
```bash
oc new-build --strategy=docker --binary --name <app name>
oc start-build <app name> --from-dir . --exclude='(^|\/)(.git|.venv|.tox)(\/|$)' --wait=true
oc new-app <app name>
oc expose svc/<app name>
```

1. (workaround) Set correct service port
```bash
oc get route <app name>
oc patch route <app name> -p '{"spec":{"port":{"targetPort": "7080-tcp"}}}'
```

## Testing the completion API

:information_source: A tunnel from localhost:7080 to remote-container-host:7080 is required when running the container using podman-remote.

Request:

```bash
# Post a request using curl
curl -X 'POST' \
  'http://127.0.0.1:8000/api/ai/completions/' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
    "context": "---\n- hosts: all\n  tasks:\n  - name: Install nginx and nodejs 12 Packages\n", "prompt": "Install nginx and nodejs 12 Packages"
    }'
```

Response:

```json
{
  "predictions": [
    "- name: ansible Convert instance config dict to a list\n      set_fact:\n        ansible_list: \"{{ instance_config_dict.results | map(attribute='ansible_facts.instance_conf_dict') | list }}\"\n      when: server.changed | bool\n"
  ]
}
```

## Test cases

Work in progress
