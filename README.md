# Ansible Wisdom service

Note: This repository is under active development and is not yet ready for production use.

##  Running server locally

### Host

1. Install all the dependencies using
```
pip install -r requirements.txt
```

1. Copy the latest checkpoint under `.checkpoint/latest` directory within
the root folder of the project, alternatively, edit the variable `ANSIBLE_WISDOM_AI_CHECKPOINT_PATH` in `ansible_wisdom/main/settings/development.py` file to point to the checkpoint location on disk.

1. Run the server using
```bash
cd ansible_wisdom
HF_DATASETS_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python manage.py runserver
```

1. this will start the application at `http://127.0.0.1:8000/`

### Container

1. Generate model archive, build container and run server
```bash
export MODEL_PATH=./model/wisdom
make mode-archive
make container
make run-server
```

### OpenShift

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
oc start-build <app name> --from-dir . --exclude='(^|\/)(.git|.venv|.tox)(\/|$)'
oc new-app <app name>
oc expose svc/<app name>
oc get builds
```

1. (workaround) Set correct service port
```bash
oc get route <app name>
oc patch route <app name> -p '{"spec":{"port":{"targetPort": "7080-tcp"}}}'
```

## Posting a request

Post a request using curl

### Host

```bash
curl -X 'POST' \
  'http://127.0.0.1:8000/api/completions/' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  		"context": "---\n- hosts: all\n  tasks:\n  - name: Install nginx and nodejs 12 Packages\n", "prompt": "Install nginx and nodejs 12 Packages"
    }'
```

### Container / OpenShift

:information_source: A tunnel from localhost:7080 to remote-container-host:7080 is required when using podman-remote.

Request:
```bash
curl -X 'POST' \
  'http://127.0.0.1:7080/predictions/wisdom/' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
        "instances":[{"context": "---\n- hosts: all\n  tasks:\n  - name: Install nginx and nodejs 12 Packages\n", "prompt": "Install nginx and nodejs 12 Packages"}]
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

## TODO
-
