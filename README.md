# Ansible Wisdom service

Note: This repository is under active development and is not yet ready for production use.

This repo contains a Django application that serves Ansible task suggestions for consumption by the Ansible VSCode extension. In the future it will also serve playbook suggestions and integrate with Ansible Risk Insights, ansible lint, etc.

The Django application depends on a separate model server to perform the task suggestion predictions. There is a torchserve configuration in this repository that can be stood up for this purpose, or you can point the Django application at the dev model server running at wisdom-wisdom-dev.apps.dev.wisdom.testing.ansible.com as described below.

## Running the Django application (from container)

1. Build the container

    ```bash
    make ansible-wisdom-container
    ```

2. Start the container

    ```bash
    run-django-container
    ```

## Running the Django application (from source)

1. Clone the repository and install all the dependencies

    ```bash
    pip install -r ansible_django/requirements.txt
    ```

1. Export the host and port for the model server. Skip this step if you want to use the model server on wisdom-wisdom-dev.apps.dev.wisdom.testing.ansible.com. See [Running the model server locally](#running-the-model-server-locally) below to spin up your own model server.

    ```bash
    export ANSIBLE_AI_MODEL_MESH_HOST="http://localhost" 
    export ANSIBLE_AI_MODEL_MESH_INFERENCE_PORT=7080
    ```

1. Start the django application

    ```bash
    make run-django
    ```

## Running the model server locally

1. Clone the repository and install all the dependencies

    ```bash
    pip install -r requirements.txt
    ```

1. Copy the model to the `MODEL_PATH` folder

1. Build the model archive, build the container and start the model mesh server

    ```bash
    export MODEL_PATH=./model/wisdom
    make model-archive
    make model-container
    make run-model-server
    ```

:information_source: NOTE: to include the model archive in the container image (for running via podman-remote or on macOS)
    ```bash
    export MODEL_PATH=./model/wisdom
    export ENVIRONMENT=production
    make model-archive
    make model-container
    make run-model-server
    ```

:information_source: NOTE: If you are running the container on RHEL, SELinux will prevent you from accessing the GPUs from the container. To work around this, for now, you can run `make run-model-server SECURITY_OPT="--security-opt=label=disable"`.

:information_source: NOTE: To use a tag other than `latest`, pass a `TAG=` argument to `make model-container` and `make run-model-server`.

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

The sample request below tests the task suggestion prediction API provided by the Django application. This is the same request the VSCode extension will make.

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

You can also directly test the model server prediction API.

Request:

```bash
# Post a request using curl
curl  -X 'POST' \
  "$ANSIBLE_AI_MODEL_MESH_HOST:$ANSIBLE_AI_MODEL_MESH_INFERENCE_PORT/predictions/wisdom" \
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
    "- name: Install nginx and nodejs 12 Packages\n  apt:\n    name:\n      - nginx\n      - nodejs\n    state: latest\n"
  ]
}
```



:information_source: A tunnel from localhost:7080 to remote-container-host:7080 is required when running the container using podman-remote.

## Using the VSCode extension

Access the updated Ansible VSCode extension here: https://drive.google.com/drive/u/1/folders/1cyjv_Ljz9I2IXY140S7_fjQsqZtxr_sg
Review the screen recording for instruction on configuring the extension to access your running wisdom service.

## Test cases

Work in progress
