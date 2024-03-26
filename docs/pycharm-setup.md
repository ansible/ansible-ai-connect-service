# PyCharm Debug Setup for Wisdom Service

By Tami Takamiya (last update: 2024.3.21)

## Summary

This is a memo on how to debug Wisdom service using PyCharm. Even though
descriptions here are very specific to PyCharm, they should be able to
be applied to other environments, e.g. VSCode + MacOS with minor modifications.

The instructions presented here were tested using
- PyCharm 2023.3.4 (Community Edition),
- Fedora Linux 39 (Workstation Edition), and
- Lenovo ThinkPad X1 Carbon Gen 9

## Setup for Development

The [README.md](../README.md) file describes the required steps
for running Wisdom Service using docker (or podman)-compose. This document assumes that you have completed
them and can run Wisdom Service using docker (or podman)-compose.

> [!NOTE]
> This document contains some duplicated information that is found in the README.md file.

Among the steps found in the README.md file, the
[Authenticating with the completion API](../README.md#authenticating-with-the-completion-api)
section is important, i.e. you need to create your own OAuth App
at [https://github.com/settings/developers](https://github.com/settings/developers).

> [!IMPORTANT]
> Initially we were using GitHub Team authentication. Now we support GitHub (without "Team") authentication and
> it is recommended to create your own OAuth App for GitHub authentication. Differences in setups for GitHub
> Team and GitHub authentications are in:
>
> | Item | GitHub team | GitHub |
> |------|-------------|--------|
> | Authorization callback URL | http://localhost:8000/complete/github-team/ | http://localhost:8000/complete/github/ |
> | Environment variables |- SOCIAL_AUTH_GITHUB_TEAM_KEY<br>- SOCIAL_AUTH_GITHUB_TEAM_SECRET |- SOCIAL_AUTH_GITHUB_KEY<br>- SOCIAL_AUTH_GITHUB_SECRET |


### Model Server

This document assumes that you are using a local llama.cpp model server, whose setup procedure is described in
the
 [Connect to a local model server](../README.md#connect-to-a-local-model-server) section
of the README.md file.

### Install PyCharm

[PyCharm](https://www.jetbrains.com/pycharm/) is an IDE made by JetBrains for Python development. Even though there is nothing wrong to use
VSCode for Python development, if you are (were) a Java developer like me and familiar with IntelliJIDEA,
you may like PyCharm over VSCode 😀

There are several ways to install PyCharm. If you are using RHEL/Fedora, avoid installing using Snap because
a debug feature cannot be installed if PyCharm is installed with Snap. I installed PyCharm using
[JetBrains Toolbox](https://www.jetbrains.com/toolbox-app/).

> [!WARNING]
> I tried to install PyCharm using Flatpak on my Fedora 38, but the installation was not successful
> and installed Toolbox instead.

### podman-compose (or docker-compose) for running backend servers

Our docker-compose setup ([compose.yaml](../tools/docker-compose/compose.yaml)) runs Wisdom Django service with several backend services
(Postgres, Prometheus and Grafana) in containers. For debugging Wisdom service, we want to run Wisdom
service directly from code with running backend services in containers.

> [!NOTE]
> While docker-compose setup runs Wisdom Django service with uwsgi, the setup presented here
> does not use uwsgi and some behaviors at runtime are different.

With [PR #89](https://github.com/ansible/ansible-wisdom-service/pull/89), we added a separate compose YAML file
([compose-backends.yaml](../tools/docker-compose/compose-backends.yaml)) and added two new
Makefile targets for the new YAML file, i.e., for running backend services, type:
```bash
make start-backends
```

For stopping backend services, type:
```bash
make stop-backends
```

> [!NOTE]
> The volumes used by Postgres DB persist after stopping backends.

You can look at them with the podman volume ls command:
```bash
podman volume ls
```
Output:
```bash
DRIVER      VOLUME NAME
local       b67b9220656a9a6d6c95c9dd4769d34fc3d2813491398c6d0c436d6c6069343d
local       bccb83160e96d816c6fc37ae212b008aa0cfffb69cc3fffc43528ef7d8626999
```


If you want to start your local wisdom-service from a clean state, remove them before running backends
with the podman volume rm command:

```bash
podman volume ls -q | xargs podman volume rm
```


## Run chcon (SELinux)

Although this instruction is for running Django service from source, you may want to run Django service
from podman-compose (or docker-compose) using [tools/docker-compose/compose.yaml](../tools/docker-compose/compose.yaml) file.
For running Django service from the compose file, you need to run following three chcon commands:

```bash
chcon -t container_file_t -R ansible_wisdom/
chcon -t container_file_t -R prometheus/
```

## PyCharm Python Setup

As of writing this (2024.3.21), the project is using Python version 3.9 because torch and torchvision
libraries are dependent on the specific version of Python.

It is recommended to use a separate virtual environment for your development. It can be configured with

1. Go to Settings page (on Linux it is File > Settings)
2. Open Project: ansible-wisdom-service > Python Interpreter and click Add Interpreter
![](images/pycharm-image10.png)
3. Select Virtual Environment and and set Base interpreter, then click OK
![](images/pycharm-image13.png)

It is also important to run
```bash
pip3 install -e '.[test]'
```
This command set up your Python environment for development and test. It creates `venv/bin/wisdom-manage`
script, which is required to run some `Makefile` targets referenced in this document.


## One-time DB Setup

After starting backend services with `make start-backends` **for the first time after a new DB
is created**, run
```bash
make create-application
```
This will execute following four targets as dependencies defined in `Makefile` for one-time DB setup:

- `migrate`
- `create-cachetable` (depends on `migrate`)
- `create-superuser` (depends on `create-cachetable`)
- `create-application` (depends on `create-superuser`)

These are needed for the following reasons:

- `migrate`: When Wisdom Service is running with docker (or podman) compose,
Django’s DB migration (manage.py migrate) is automatically executed,
but for running Wisdom Service from source, we need to manually
execute DB migration before running.
- `create-cachetable`: Since we use DB for caching
instead of a dedicated service such as Redis, a table for caching is need
to be created.
- `create-superuser`: This target creates a superuser for using Django’s admin UI.
- `create-application`: For using the local development environment with Ansible VSCode extension, the
setup of an authentication application is needed.

> [!WARNING]
> By default, `make create-superuser` creates a Django superuser with:
> - username: admin
> - email: admin@example.com
> - password: somesecret
>
> You can override the default password by defining the `DJANGO_SUPERUSER_PASSWORD`
> environment variable before running the command.


## PyCharm Run Configurations

We are going to create following run configurations:

1. runserver
1. test

`runserver` is for running Wisdom Service and `test` is for running unit tests.

### .env

For reusing the same set of environment variables, it is recommended to define a `.env` file

> [!Note]
> Previous versions of PyCharm needed to use the [EnvFile](https://plugins.jetbrains.com/plugin/7861-envfile) PyCharm plugin for enabling `.env` file suport. Now PyCharm has its own built-in `.env` file support.

You can copy & paste following lines and add your GitHub key/secret to your .env file:

```bash
ANSIBLE_AI_DATABASE_HOST=localhost
ANSIBLE_AI_DATABASE_NAME=wisdom
ANSIBLE_AI_DATABASE_PASSWORD=wisdom
ANSIBLE_AI_DATABASE_USER=wisdom
ARI_KB_PATH=../ari/kb/
DJANGO_SETTINGS_MODULE=main.settings.development
ENABLE_ARI_POSTPROCESS=False
PYTHONUNBUFFERED=1
SECRET_KEY=somesecret
SOCIAL_AUTH_GITHUB_KEY=(your key here)
SOCIAL_AUTH_GITHUB_SECRET=(your secret here)
ANSIBLE_AI_MODEL_MESH_API_TYPE=llamacpp
ANSIBLE_AI_MODEL_NAME=mistral-7b-instruct-v0.2.Q5_K_M.gguf
ANSIBLE_AI_MODEL_MESH_HOST=http://localhost
ANSIBLE_AI_MODEL_MESH_INFERENCE_PORT=8080
ENABLE_ARI_POSTPROCESS=False
```

> [!TIP]
> The example shown above uses local llama.cpp server with Mistral 7B Instruct model. For using a other type of model server that provides prediction results, you need to set extra environment variables for a client type that is used to connect to the model server. Please take a look at the [README](../README.md) for more details.

### runserver configuration

Go to Run > Edit Configurations menu and create the `runserver` configuration:

- Script path: point to `ansible_wisdom/manage.py`
- Script arguments: `runserver --noreload`
- Working directory: point to `ansible_wisdom`
- Paths to '.env' files: path to point your `.env` file

![runserver](./images/pycharm-runserver-config.png)

### test configuration

The `test` configuration is similar to the `runserver` configuration. The only difference is
in Script arguments:

- Script path: point to `ansible_wisdom/manage.py`
- Script arguments: `test`
- Working directory: point to `ansible_wisdom`
- Paths to '.env' files: path to point your `.env` file

![test](./images/pycharm-test-config.png)


### Tips to run specific test cases

If you specify only test in the Parameters, all unit test cases are executed. You can add a class or a method to the Script arguments to limit the test cases to be executed.  For example,

```bash
test users.tests.test_users.TestUserSeat
```

will execute tests defined in the TestUserSeat class only and

```bash
test users.tests.test_users.TestUserSeat.create_user
```

will execute the create_user method only.

"Copy Reference" ("Copy/Paste Special > Copy Reference from the context menu or Ctrl+Alt+Shift+C in shortcut) is convenient to copy the fully qualified class/method name.

## Execution

Once both the runserver and test configurations are created, make sure the backend servers are running in containers and run `make create-application` if you have not executed it yet.

> [!IMPORTANT]
> If you removed persistent volumes before running backends, you need to run `make create-application` again to initialize DB.

Then run `runserver` in Debug mode with PyCharms Run > Debug… menu. Console output would be like:

```bash
/home/ttakamiy/git/ansible/ansible-wisdom-service/venv/bin/python /home/ttakamiy/git/ansible/ansible-wisdom-service/ansible_wisdom/manage.py runserver --noreload
Performing system checks...

System check identified no issues (0 silenced).
March 21, 2024 - 16:35:46
Django version 4.2.11, using settings 'main.settings.development'
Starting development server at http://127.0.0.1:8000/
Quit the server with CONTROL-C.
```


If you open your web browser and point to [http://localhost:8000/](http://localhost:8000/), you see:

![](images/pycharm-image5.png)

DON'T CLICK Log in HERE! If you do so, you'll see
![](images/pycharm-image1.png)

then you'll see

![](images/pycharm-image15.png)

What you need is to open VSCode, install Ansible Plugin, and configure Lightspeed URL
to [http://localhost:8000/](http://localhost:8000/) (note it's http, not https)


![](images/pycharm-image16.png)

Click the Ansible icon and click Connect:

![](images/pycharm-image4.png)

Click Allow to sign in:

![](images/pycharm-image7.png)

then you will see the login screen with the "Log in with GitHub" button.
Click the button and it will guide you to the Terms of Use page, etc.

![](images/pycharm-image3.png)

If everything went well, you'll see your GitHub ID on the web browser screen:

![](images/pycharm-image11.png)

From that point, you can start debugging, i.e. set breakpoint, view variables etc. Have fun!
