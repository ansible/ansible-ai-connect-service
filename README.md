# Ansible Lightspeed with Watson Code Assistant service

Note: This repository is under active development and is not yet ready for production use.

This repo contains a Django application that serves Ansible task suggestions for consumption by the Ansible VSCode extension. In the future it will also serve playbook suggestions and integrate with Ansible Risk Insights, ansible lint, etc.

The Django application depends on a separate model server to perform the task suggestion predictions. There is a torchserve configuration in this repository that can be stood up for this purpose, or you can point the Django application at the dev model server running at model.wisdom.testing.ansible.com as described below.

## Using pre-commit

Pre-commit should be used before pushing a new PR.
To use pre-commit, you need to first install the pre-commit package and its dependencies by running:

```bash
pip install -r requirements-dev.txt
```


To install pre-commit into your git hooks and run the checks on every commit, run the following each time you clone this repo:

```bash
pre-commit install
```


To update the pre-commit config to the latest repos' versions and run the precommit check across all files, run:

```bash
pre-commit autoupdate && pre-commit run -a
```

## Updating the Python dependencies

We are now using pip-compile in order to manage our Python
dependencies.

The specification of what packages we need now live in the
requirements.in and requirements-dev.in files.  Use your preferred
editor to make the needed changes in those files, then run

```bash
make pip-compile
```

This will spin up a container and run the equivalent of these commands
to generate the updated files:

```bash
pip-compile requirements.in
pip-compile requirements-dev.in
```

These commands will produce fully populated and pinned requirements.txt and
requirements-dev.txt files, containing all of the dependencies of
our dependencies involved.  Due to differences in architecture and
version of Python between developers' machines, we do not recommend
running the pip-compile commands directly.


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
`ansible_wisdom/`, `prometheus/` and `ari/` directories:

```bash
chcon -t container_file_t -R ansible_wisdom/
chcon -t container_file_t -R prometheus/
chcon -t container_file_t -R grafana/
chcon -t container_file_t -R ari/
```
Also run `chmod` against the `ari/` directory so that ARI can
write temporary data in it:
```bash
chmod -R 777 ari/
```

Recreating the dev containers might be useful:
``` bash
$ make docker-compose-clean
```

It may be necessary to recreate the dev image if anything has changed in the nginx settings:
``` bash
$ docker rmi docker-compose_django_1
```

Create a local admin user:
``` bash
$ make docker-create-superuser
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
pip install -r requirements.txt
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

## Running Backend Services (from container)

If you want to run backend services from container, run the following steps. This
is convenient for debugging the Django application without installing backend
services on your local machine.

1. Build the container

    ```bash
    make ansible-wisdom-container
    ```

2. Start backend services.

    ```bash
    make run-backends
    ```

For terminating backend services, run `make stop-backends`.

Note that you need to run `manage.py migrate` and `manage.py createcachetable` to set up DB
before running the Django application from source,

The setup for debugging is different depending on the Python development tool.
For PyCharm, please look at [this document](https://docs.google.com/document/d/1QkdvtthnvdHc4TKbWV00pxnEKRU8L8jHNC2IaQ950_E/edit?usp=sharing).

## Deploy the service via OpenShift S2I
```
oc new-build --strategy=docker --binary --name wisdom-service
oc start-build wisdom-service --from-dir . --exclude='(^|\/)(.git|.venv|.tox|model)(\/|$)' --wait=true
oc new-app wisdom-service
```

## Testing the completion API

The sample request below tests the task suggestion prediction API provided by the Django application. This is the same request the VSCode extension will make.

Request:

```bash
# Post a request using curl
curl -X 'POST' \
  'http://127.0.0.1:8000/api/v0/ai/completions/' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
    "prompt": "---\n- hosts: all\n  tasks:\n  - name: Install nginx and nodejs 12 Packages\n"
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

Access the updated Ansible VSCode extension here:
https://drive.google.com/drive/u/1/folders/1cyjv_Ljz9I2IXY140S7_fjQsqZtxr_sg

In order to successfully connect to your local dev environment using
the plugin, you need to create the OAuth2 application in Django.  Open
a shell session in the Django container using

```bash
docker exec -it docker-compose_django_1 bash
```

and then run the Django command to create the application:

```bash
  wisdom-manage createapplication \
    --name "Ansible Lightspeed for VS Code" \
    --client-id Vu2gClkeR5qUJTUGHoFAePmBznd6RZjDdy5FW2wy \
    --redirect-uris "vscode://redhat.ansible vscodium://redhat.ansible vscode-insiders://redhat.ansible" \
    public authorization-code
```

This sets up a matching client ID to the one that is coded directly
into the VSCode extension.

Review the screen recording for instruction on configuring the VSCode
extension to access your running wisdom service.

Note: If, after running ```python manage.py runserver``` you encounter an AssertionError, use the following command: ```python manage.py runserver --noreload```. You can also disable it by adding `INSTALLED_APPS = [i for i in INSTALLED_APPS if i not in ["django_prometheus"]]` to the `ansible_wisdom/main/settings/development.py` file.


## Authenticating with the completion API

GitHub authentication has been added for the pilot. Pilot access will be limited to a specific team. Settings are currently hardcoded to the wisdom-contrib team, but a new team will be created for the pilot.

To test GitHub authentication locally, you will need to create a new OAuth App at https://github.com/settings/developers. Provide an Authorization callback URL of http://localhost:8000/complete/github-team/. Export Update `SOCIAL_AUTH_GITHUB_TEAM_KEY` and `SOCIAL_AUTH_GITHUB_TEAM_SECRET` before starting your app. `SOCIAL_AUTH_GITHUB_TEAM_KEY` and `SOCIAL_AUTH_GITHUB_TEAM_SECRET` correspond to the Client ID and Client Secret respectively, both of which are provided after creating a new OAuth App. If you are running with the compose [development environment](#development-environment) described below, put these env vars in a .env file in the `tools/docker-compose` directory.


Once you start the app, navigate to http://localhost:8000/ to log in. Once authenticated, you will be presented with an authentication token that will be configured in VSCode (coming soon) to access the task prediction API.

To get an authentication token, you can run the following command:

```bash
podman exec -it docker-compose-django-1 wisdom-manage createtoken --create-user
```
Note: If using `docker-compose`, the container might have a different name such as `docker-compose-django-1` in which case the command would be:
```bash
podman exec -it docker-compose-django-1 wisdom-manage createtoken --create-user
```


- `my-test-user` will be create for you
- `my-token` is the name of the token

To get an authentication token without logging in via GitHub, you also:

1. create an admin user
2. navigate to http://localhost:8000/admin/
3. and log in with your superuser credentials
4. then navigate to http://localhost:8000/admin/oauth2_provider/accesstoken/
5. create a new token.

To test the API with no authentication, you can empty out `REST_FRAMEWORK.DEFAULT_PERMISSION_CLASSES` in base.py.

## Enabling postprocess with ARI

You can enable postprocess with [Ansible Risk Insight (ARI)](https://github.com/ansible/ansible-risk-insight) for improving the completion output just by following these 2 steps below.

1. Set the environment variable `ENABLE_ARI_POSTPROCESS` to True

    ```bash
    $ export ENABLE_ARI_POSTPROCESS=True
    ```


2. Prepare `rules` and `data` directory inside `ari/kb` directory.

    `rules` should contain mutation rules for the postprocess, you can refer to [here](https://github.com/ansible/ari-metrics-for-wisdom/tree/main/rules) for some examples.

    `data` should contain the backend data for ARI. We will host this data somewhere in the future, but currently this file must be placed manually if you want to enable the postprocess.

    Once the files are ready, the `ari/kb` directory should look like this.

    ```bash
    ari/kb/
    ├── data
    │   ├── collections
    │   └── indices
    └── rules
        ├── W001_module_name_metrics.py
        ├── W002_module_key_metrics.py
        ├── ...
    ```

Then you can build the django image or just run `make docker-compose`.

## Application metrics as a Prometheus-style endpoint

We enabled the Prometheus endpoint to scrape the configuration and check the service status to build observability into the Lightspeed service for monitoring and measuring its availability.

To provide feedback for operational needs as well as for continuous service improvement.

## Swagger UI, ReDoc UI and OpenAPI 3.0 Schema

### Swagger UI

Swagger UI is available at http://localhost:8000/api/schema/swagger-ui/ **in
the development environment only**.
- **Note:** It is not enabled in the production environment regardless of any settings.


If you want to test Lightspeed APIs using Swagger UI,

1. Open http://localhost:8000/ and get an authentication token by
following the instructions described in the
[Authenticating with the completion API](#authenticating-with-the-completion-api)
section.
2. Open http://localhost:8000/api/schema/swagger-ui/
3. Click the **Authorize** button.
4. Input the authentication token for the tokenAuth as it is.
You do not need to add any prefixes, such as `Bearer ` or `Token `.
5. Click **Authorize**.
6. Click **Close** to go back to the Swagger UI page.
7. Expand a section for the API that you want to try and click **Try it out**.
8. Input required parameters (if any) and click **Execute**.

### ReDoc UI

Another OpenAPI UI in the ReDoc format is also available at  http://localhost:8000/api/schema/redoc/
**in the development environment only**.

### OpenAPI 3.0 Schema

The static OpenAPI Schema YAML file is stored as
[/tools/openapi-schema/ansible-wisdom-service.yaml](https://github.com/ansible/ansible-wisdom-service/blob/main/tools/openapi-schema/ansible-wisdom-service.yaml) in this repository.

When you make code changes, please update the static OpenAPI Schema YAML file
with the following steps:

1. Update API descriptions.  See [this doc](https://docs.google.com/document/d/1iF32yui3JTG808GhInN7CUTEn4Ocimed1szOn0N0P_E/edit#heading=h.sufj9xfpwkbn)
to find where to update.
2. Make sure the API version is updated in [development.yaml](https://github.com/ansible/ansible-wisdom-service/blob/7a9669be1ac5b037d1bd92793db48e6aed15bb4e/ansible_wisdom/main/settings/development.py#L38)
3. Run `make update-openapi-schema` in the project root.
4. Checkin the updated OpenAPI Schema YAML file with your API changes.

Also a dynamically generated OpenAPI 3.0 Schema YAML file can be downloaded either:

- Click the /api/schema/ link on Swagger UI, or
- Click the Download button on ReDoc UI

## Test cases

Unit-tests are based on Python's [unittest library](https://docs.python.org/3/library/unittest.html#module-unittest) and rely on [Django REST framework APIClient](https://www.django-rest-framework.org/api-guide/testing/#apiclient).

### Unit-test Guidelines

-  Use `reverse()`:

    Please make use of Django's [reverse() function](https://docs.djangoproject.com/en/4.1/ref/urlresolvers/#reverse) to specify which view you are hitting.
    If and when we change the path some endpoint is at, the person making the change will appreciate not having to search and replace all of those strings.

    Additionally if you are hitting the same endpoint over a bunch of methods on the same test class, you can always store the results of `reverse()` in an attribute and make use of that, to reduce the repetition.

### Execute Unit Tests and Measure Code Coverage

#### Preparation

For running Unit Tests in this repository, you need to
have backend services (Postgres DB and Redis) running.
[Running them from container](#running-backend-services--from-container-)
is one handy way for that requirement.

For getting the unit test code coverage,
install the `coverage` module, which is included
in `requirements-dev.txt` with the instructions in the
[Using pre-commit](#using-pre-commit) section.

#### Use make

The easiest way to run unit tests and measure code coverage report is to run
```commandline
make code-coverage
```
If the execution was successful, results in HTML are showin in Chrome.

#### Running Unit Tests from Command Line or PyCharm

For executing unit tests from command lline,
You need to set some environment variables
that are read by Lightspeed Service.
If you are using PyCharm
for development, you can use [the EnvFile plugin](https://plugins.jetbrains.com/plugin/7861-envfile)
 with the following `.env` file:

```commandline
ANSIBLE_AI_DATABASE_HOST=localhost
ANSIBLE_AI_DATABASE_NAME=wisdom
ANSIBLE_AI_DATABASE_PASSWORD=wisdom
ANSIBLE_AI_DATABASE_USER=wisdom
ARI_KB_PATH=../ari/kb/
DJANGO_SETTINGS_MODULE=main.settings.development
ENABLE_ARI_POSTPROCESS=True
PYTHONUNBUFFERED=1
SECRET_KEY=somesecret
```
Note that this `.env` file assumes that the Django
service is executed in the `ansible_wisdom` subdirectory
as `ARI_KB_PATH` is defined as `../ari/kb`.

If you want to run unit tests from command line,
export those variables as environment variables.
If variables are defined in `.env` file,
it can be done with following commands:

```commandline
set -o allexport
source .env
set +o allexport
```

After environment variables are set, you can issue following commands

```commandline
cd ansible_wisdom
python3 manage.py test
```
to run unit tests.

#### Measuring Code Coverage from Command Line

If you want to get code coverage by
running unit tests from command line,
set environment variables listed in the section above
and run following commands:

```commandline
cd ansible_wisdom
coverage run --rcfile=../setup.cfg manage.py test
```

After tests completed, run
```commandline
coverage report
```
for showing results on console, or
```commandline
coverage html
```
to generate HTML reports under `htmlcov` directory.
