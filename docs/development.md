# Development guide

This guide covers how to configure, test, and contribute to the Ansible AI
Connect service. For an overview and a quick start, see the
[README](../README.md).

## Project structure

| Path                              | Description                          |
|-----------------------------------|--------------------------------------|
| `ansible_ai_connect`              | The service (Django)                 |
| `ansible_ai_connect_admin_portal` | Admin portal UI (React)              |
| `ansible_ai_connect_chatbot`      | Chatbot UI (React)                   |
| `aap_chatbot`                     | Chatbot UI package for the AAP UI    |

Each UI directory has its own README with build and test steps:
[admin portal](../ansible_ai_connect_admin_portal/README.md),
[chatbot](../ansible_ai_connect_chatbot/README.md), and
[AAP chatbot package](../aap_chatbot/README.md).

## Configure the service

You configure the service with environment variables. When you use the
compose environment from the README, put them in
`tools/docker-compose/.env`.

### Model servers

`ANSIBLE_AI_MODEL_MESH_CONFIG` tells the service which model server to use for
each feature. See the
[model configuration examples](./config/examples/README-ANSIBLE_AI_MODEL_MESH_CONFIG.md).

The compose environment does not include a model server. Point
`ANSIBLE_AI_MODEL_MESH_CONFIG` at one you already run, such as Ollama.

To use a Mistral 7B Instruct model on a local
[llama.cpp](https://github.com/ggerganov/llama.cpp) server:

1. Download the Mistral 7B Instruct
   [llamafile](https://github.com/Mozilla-Ocho/llamafile?tab=readme-ov-file#other-example-llamafiles).
1. Make it executable and run it. Replace `$YOUR_REAL_IP` with your machine's
   IP address, not `127.0.0.1` or `localhost`:

   ```bash
   chmod +x ./mistral-7b-instruct-v0.2-Q5_K_M-server.llamafile
   ./mistral-7b-instruct-v0.2-Q5_K_M-server.llamafile --host $YOUR_REAL_IP
   ```

1. Set `ANSIBLE_AI_MODEL_MESH_CONFIG` to use it. See the
   [examples](./config/examples/README-ANSIBLE_AI_MODEL_MESH_CONFIG.md).

### IBM watsonx Code Assistant API keys

The service stores IBM watsonx Code Assistant (WCA) API keys in a secret
backend. For local development, use the dummy backend:

```bash
WCA_SECRET_BACKEND_TYPE="dummy"
WCA_SECRET_DUMMY_SECRETS="11009103:valid"
```

In this example, `11009103` is your organization ID and `valid` is the model.
To set both the API key and the model, use this format:

```bash
WCA_SECRET_DUMMY_SECRETS='11009103:ibm_api_key<sep>model_id<|sepofid|>model_name'
```

Hosted deployments (`DEPLOYMENT_MODE=saas`) store the keys in AWS Secrets
Manager instead:

```bash
DEPLOYMENT_MODE=saas
WCA_SECRET_MANAGER_ACCESS_KEY=<aws-access-key>
WCA_SECRET_MANAGER_SECRET_ACCESS_KEY=<aws-secret-access-key>
WCA_SECRET_MANAGER_KMS_KEY_ID=<kms-key-id-or-alias>
WCA_SECRET_MANAGER_PRIMARY_REGION=<primary-region>
WCA_SECRET_MANAGER_REPLICA_REGIONS=<replica-regions>
```

The AWS user needs permission to read and write these secrets. The KMS key must
be either a multi-region key (when you use its ID) or a key with the same alias
in the primary and replica regions. When you use an alias, add the `alias/`
prefix, for example `alias/my-key`.

### Ansible Lint post-processing

To improve code suggestions with
[Ansible Lint](https://github.com/ansible/ansible-lint), set
`ENABLE_ANSIBLE_LINT_POSTPROCESS=True`. This feature is available only to
commercial users.

### Debug mode

To run the service in debug mode, set `DEBUG=True`. The service listens on
<http://127.0.0.1:8000>.

### Metrics

The service exposes Prometheus metrics at `/metrics`.

## Connect VS Code

1. Install the
   [Ansible extension](https://marketplace.visualstudio.com/items?itemName=redhat.ansible).
1. Create the OAuth2 application that the extension signs in with. Open a shell
   in the Django container:

   ```bash
   podman exec -it docker-compose_django_1 bash
   ```

   Then create the application:

   ```bash
   wisdom-manage createapplication \
     --name "Ansible AI Connect for VS Code" \
     --client-id Vu2gClkeR5qUJTUGHoFAePmBznd6RZjDdy5FW2wy \
     --redirect-uris "vscode://redhat.ansible vscodium://redhat.ansible vscode-insiders://redhat.ansible code-oss://redhat.ansible checode://redhat.ansible" \
     public authorization-code
   ```

   The client ID matches the one built into the extension. If you run the
   service from source instead of containers, run `make create-application`.

1. In VS Code, open **File > Preferences > Settings** (**Code > Settings** on
   macOS) and search for `Lightspeed`.
1. For both **User** and **Workspace**, set:
   - `Ansible > Lightspeed`: **Enabled**
   - `Ansible > Lightspeed: URL`: `http://localhost:8000`
   - `Ansible > Lightspeed: Suggestions`: **Enabled**

The container name depends on your compose provider:
`docker-compose_django_1` with podman-compose, or `docker-compose-django-1`
with docker-compose.

If `python manage.py runserver` fails with an `AssertionError`, run
`python manage.py runserver --noreload` instead. You can also remove
`django_prometheus` from `INSTALLED_APPS` in
`ansible_ai_connect/main/settings/development.py`.

## Authentication

The service supports GitHub and Red Hat sign-in.

### GitHub

1. Create an OAuth app at <https://github.com/settings/developers>. Set the
   authorization callback URL to `http://localhost:8000/complete/github/`.
1. Set `SOCIAL_AUTH_GITHUB_KEY` to the app's client ID and
   `SOCIAL_AUTH_GITHUB_SECRET` to its client secret. With the compose
   environment, add them to `tools/docker-compose/.env`.

> **Warning:** The host name in your browser must match the host name in the
> callback URL. If you open `http://127.0.0.1:8000`, use `127.0.0.1` in the
> callback URL too, not `localhost`.

### Red Hat

Red Hat sign-in uses Red Hat SSO. Set these variables:

```bash
export SOCIAL_AUTH_OIDC_OIDC_ENDPOINT="https://sso.redhat.com/auth/realms/redhat-external"
export SOCIAL_AUTH_OIDC_KEY="<client-id>"
export SOCIAL_AUTH_OIDC_SECRET="<client-secret>"
```

The `Makefile` sets the first two for you. You always need to set
`SOCIAL_AUTH_OIDC_SECRET` yourself.

### Get an API token

After you start the service, open <http://localhost:8000/> and sign in.

To create a user and a token from the command line:

```bash
podman exec -it docker-compose_django_1 \
  wisdom-manage createtoken --username my-test-user --token-name my-token --create-user
```

To create a token in the Django admin instead:

1. Create a superuser.
1. Open <http://localhost:8000/admin/> and sign in.
1. Open <http://localhost:8000/admin/oauth2_provider/accesstoken/> and add a
   token.

To call the API without authentication during development, empty
`REST_FRAMEWORK.DEFAULT_PERMISSION_CLASSES` in
`ansible_ai_connect/main/settings/base.py`.

## Try the API

### Code suggestions

This is the same request the VS Code extension sends:

```bash
curl -X POST 'http://127.0.0.1:8000/api/v0/ai/completions/' \
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

### Swagger UI and ReDoc

In the development environment only, you can browse the API at:

- Swagger UI: <http://localhost:8000/api/schema/swagger-ui/>
- ReDoc: <http://localhost:8000/api/schema/redoc/>

Production never enables them, whatever the settings.

To call the API from Swagger UI:

1. [Get an API token](#get-an-api-token).
1. Open Swagger UI and click **Authorize**.
1. Paste the token into **tokenAuth** as is, with no `Bearer` or `Token`
   prefix, and click **Authorize**. Then click **Close**.
1. Expand an API, click **Try it out**, fill in any parameters, and click
   **Execute**.

## OpenAPI schema

The static schema lives at
[`tools/openapi-schema/ansible-ai-connect-service.yaml`](../tools/openapi-schema/ansible-ai-connect-service.yaml).
You can also download a live copy from the `/api/schema/` link in Swagger UI
or the **Download** button in ReDoc.

When you change the API, update the static schema:

1. Check that the API metadata (description, version, and the `TAGS` that
   group the APIs) is accurate in the `SPECTACULAR_SETTINGS` variable in
   [`ansible_ai_connect/main/settings/development.py`](../ansible_ai_connect/main/settings/development.py).
1. Run the service locally.
1. Run `make update-openapi-schema` from the repository root.
1. Commit the updated schema with your API changes.

CI validates the schema against the OpenAPI 3.0 specification on every pull
request and push to `main`. The check does not block merges yet, but fix any
errors it reports. To validate locally:

```bash
pip install -e '.[dev]'

# Terminal 1: start the service
make run-server

# Terminal 2: validate
make validate-openapi-schema
```

## Testing

Unit tests use Python's
[unittest](https://docs.python.org/3/library/unittest.html#module-unittest)
and the
[Django REST framework APIClient](https://www.django-rest-framework.org/api-guide/testing/#apiclient).

When a test calls an endpoint, use Django's
[`reverse()`](https://docs.djangoproject.com/en/4.1/ref/urlresolvers/#reverse)
instead of a hard-coded path, so tests keep working when paths change. If many
tests in a class call the same endpoint, store the result of `reverse()` in an
attribute.

### Before you start

The tests need Postgres, Prometheus, and Grafana. To run them in containers:

```bash
make start-backends
```

Install the development dependencies, which include `coverage`:

```bash
pip install -e '.[dev]'
```

### Run the tests

The easiest way is `make`, which sets default values for you:

```bash
make test
```

To run one file, class, or method, set `WISDOM_TEST`:

```bash
WISDOM_TEST="ansible_ai_connect.main.tests.test_views.LogoutTest" make test
```

To run the tests without `make`, create a `.env` file:

```bash
LAUNCHDARKLY_SDK_KEY=flagdata.json
ANSIBLE_AI_DATABASE_HOST=localhost
ANSIBLE_AI_DATABASE_NAME=wisdom
ANSIBLE_AI_DATABASE_PASSWORD=wisdom
ANSIBLE_AI_DATABASE_USER=wisdom
DJANGO_SETTINGS_MODULE=ansible_ai_connect.main.settings.development
PYTHONUNBUFFERED=1
SECRET_KEY=somesecret
```

Then load it and run the tests from the repository root:

```bash
set -o allexport
source .env
set +o allexport

python3 -m ansible_ai_connect.manage test ansible_ai_connect
```

In PyCharm, you can load the same `.env` file in your run configuration. See
the [PyCharm setup guide](./pycharm-setup.md).

### Measure code coverage

To run the tests, build an HTML report, and open it in Chrome:

```bash
make code-coverage
```

To do it by hand, load the `.env` file as shown above, then run:

```bash
coverage run --rcfile=setup.cfg -m ansible_ai_connect.manage test ansible_ai_connect
coverage report   # print to the console
coverage html     # write an HTML report to htmlcov/
```

## Contributing

Submit all changes as pull requests against `main`.

1. Fork the repository, or create a feature branch if you have write access.
1. Make your changes.
1. Run the [pre-commit checks](#pre-commit) and the [tests](#testing).
1. Open a pull request against `main`, or against a `stable-*` branch for a
   backport.
1. Wait for CI to pass and for a review.

### CI checks

These checks run on pull requests. Get them green before you ask for a merge.

| Check | What it does |
|---|---|
| [pre-commit](../.github/workflows/pre-commit.yml) | Linting and formatting |
| [Code coverage](../.github/workflows/code_coverage.yml) | Unit tests and SonarCloud scan |
| [Pyright](../.github/workflows/pyright.yml) | Type checking |
| [pip audit](../.github/workflows/pip_audit.yml) | Python dependency security scan |
| [OpenAPI schema](../.github/workflows/code_coverage.yml) | Schema validation and drift detection |
| [uv export](../.github/workflows/uv_export.yml) | Lock file consistency |
| Admin portal: [npm audit](../.github/workflows/npm_audit.yml), [build and test](../.github/workflows/ui_compile.yml) | JavaScript dependency scan, TypeScript build, and tests |
| Chatbot: [npm audit](../.github/workflows/npm_audit_chatbot.yml), [build and test](../.github/workflows/ui_compile_chatbot.yml) | Same checks for the chatbot UI |
| AAP chatbot: [npm audit](../.github/workflows/npm_audit_aap_chatbot.yml), [build and test](../.github/workflows/ui_test_aap_chatbot.yml) | Same checks for the AAP chatbot package |

### Backports

To backport a merged pull request to a `stable-*` branch, add the label
`backport/<branch>`, for example `backport/stable-2.6`. A bot opens the
backport pull request for you.

### pre-commit

Install the development dependencies, which include pre-commit, and set up the
git hook once per clone:

```bash
pip install -e '.[dev]'
pre-commit install
```

To run all checks on all files:

```bash
pre-commit run -a
```

## Dependencies

The project uses [uv](https://github.com/astral-sh/uv) to manage Python
dependencies, like
[ansible-chatbot-stack](https://github.com/ansible/ansible-chatbot-stack). All
dependencies are in `pyproject.toml`.

To update the pinned versions after you change `pyproject.toml`:

1. Resolve the lock file locally. `uv.lock` is cross-platform, so always
   resolve it on your machine, not in a container:

   ```bash
   uv lock
   ```

1. Export `requirements.txt` for the Linux target platform:

   ```bash
   make export
   ```

   This runs the following in a container. It does not run `uv lock`:

   ```bash
   uv export --format requirements-txt --no-hashes --no-emit-project -o requirements.txt
   ```

1. Commit both files:

   - `uv.lock`: exact pinned versions.
   - `requirements.txt`: the same pins, for pip.

Security pins for transitive dependencies go in `constraint-dependencies`
under `[tool.uv]` in `pyproject.toml`. `uv lock` applies them automatically.

Development dependencies (testing, linting, and so on) are in
`[project.optional-dependencies]`. To install them:

```bash
pip install -e '.[dev]'
# or
uv pip install -e '.[dev]'
```

### Automated updates

Bots open pull requests for dependency updates in Python packages, the npm
packages of the UIs, and GitHub Actions. Security updates merge automatically
once CI passes. Other updates wait for a review.

## Deploy with OpenShift S2I

```bash
oc new-build --strategy=docker --binary --name wisdom-service
oc start-build wisdom-service --from-dir . --exclude='(^|\/)(.git|.venv|.tox|model)(\/|$)' --wait=true
oc new-app wisdom-service
```

## Back up and restore the database

With the Podman compose environment running:

```bash
./tools/scripts/dump-db.sh /tmp/my-backup.dump
./tools/scripts/restore-db.sh /tmp/my-backup.dump
```

## Troubleshooting

### Permission denied when containers start

On systems with SELinux, label the mounted directories:

```bash
chcon -t container_file_t -R ansible_ai_connect/
chcon -t container_file_t -R prometheus/
```

### Container build runs out of memory

If the Django image build fails like this, webpack ran out of memory:

```text
STEP 30/46: RUN npm --prefix /tmp/ansible_ai_connect_admin_portal run build
...
npm ERR! signal SIGKILL
```

Give your Podman machine more memory:

```bash
podman machine set --memory 8192
```

### Stale containers or images

To recreate the containers:

```bash
podman compose -f tools/docker-compose/compose.yaml down
```

If you changed the nginx settings, also remove the image so it rebuilds:

```bash
podman rmi localhost/docker-compose_django:latest
```

### Too many open files

Raise the open file limit for your shell, then try again:

```bash
ulimit -n unlimited
```

If your platform does not allow `unlimited`, use a large number instead.
