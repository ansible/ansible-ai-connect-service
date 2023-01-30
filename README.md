# Ansible Wisdom service

Note: This repository is under active development and is not yet ready for production use.

This repo contains a Django application that serves Ansible task suggestions for consumption by the Ansible VSCode extension. In the future it will also serve playbook suggestions and integrate with Ansible Risk Insights, ansible lint, etc.

The Django application depends on a separate model server to perform the task suggestion predictions. There is a torchserve configuration in this repository that can be stood up for this purpose, or you can point the Django application at the dev model server running at model.wisdom.testing.ansible.com as described below.

## Using pre-commit

Pre-commit should be used before pushing a new PR.
To use pre-commit you need to first install it and it's dependencies by running:

    ```bash
    pip install -r requirements-dev.txt
    ```

once installed you can run the hooks with:

    ```bash
    pre-commit run --all
    ```

## Full Development Environment

You can deploy a development environment using `docker-compose` or
`podman-compose`.

First, set an environment variable with your desired Django secret
key:

```bash
export SECRET_KEY=somesecretvalue
```

For convenience, we have a make target to bring up all of the
containers:

```bash
make docker-compose
```

The same result can still be accomplished manually, by running

```bash
podman-compose -f tools/docker-compose/compose.yaml up
```

or

```bash
docker-compose -f tools/docker-compose/compose.yaml up
```

Either version can be run in debug mode by exporting or adding to the
command line the variable `DEBUG_VALUE=True`.

The Django service listens on <http://127.0.0.1:8000>.

Note that there is no pytorch service defined in the docker-compose
file.  You should adjust the `ANSIBLE_AI_MODEL_MESH_HOST`
configuration key to point on an existing service.

If you get a permission denied error when attempting to start the
containers, you may need to set the permissions on the
`ansible_wisdom/` directory:

```bash
chcon -t container_file_t -R ansible_wisdom/
```

## Running the Django application standalone (from container)

1. Build the container

    ```bash
    make ansible-wisdom-container
    ```

2. Start the container

    ```bash
    make run-django-container
    ```

## Running the Django application standalone (from source)

1. Clone the repository and install all the dependencies

    ```bash
    pip install -r ansible_wisdom/requirements.txt
    ```

1. Export the host and port for the model server. Skip this step if you want to use the model server on model.wisdom.testing.ansible.com. See [Running the model server locally](#running-the-model-server-locally) below to spin up your own model server.

    ```bash
    export ANSIBLE_AI_MODEL_MESH_HOST="http://localhost"
    export ANSIBLE_AI_MODEL_MESH_INFERENCE_PORT=7080
    ```

1. Start the django application

    ```bash
    make run-django
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

## Using the VSCode extension

Access the updated Ansible VSCode extension here: https://drive.google.com/drive/u/1/folders/1cyjv_Ljz9I2IXY140S7_fjQsqZtxr_sg
Review the screen recording for instruction on configuring the extension to access your running wisdom service.

## Authenticating with the completion API

GitHub authentication has been added for the pilot. Pilot access will be limited to a specific team. Settings are currently hardcoded to the wisdom-contrib team, but a new team will be created for the pilot.

To test GitHub authentication locally, you will need to create a new OAuth App at https://github.com/settings/developers. Provide an Authorization callback URL of http://localhost:8000/complete/github-team/. Export Update `SOCIAL_AUTH_GITHUB_TEAM_KEY` and `SOCIAL_AUTH_GITHUB_TEAM_SECRET` before starting your app. If you are running with the compose [development environment](#development-environment) described below, put these env vars in a .env file in the `tools/docker-compose` directory.


Once you start the app, navigate to http://localhost:8000/ to log in. Once authenticated, you will be presented with an authentication token that will be configured in VSCode (coming soon) to access the task prediction API.

To get an authentication token without logging in via GitHub, you can navigate to http://localhost:8000/admin/ and log in with your superuser credentials, then navigate back to http://localhost:8000/ (or view your token in the admin console).

To test the API with no authentication, you can empty out REST_FRAMEWORK.DEFAULT_PERMISSION_CLASSES in base.py.

## Test cases

Work in progress
