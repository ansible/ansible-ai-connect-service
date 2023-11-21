ENVIRONMENT ?= development
TAG ?= latest

# Choose between docker and podman based on what is available
ifeq (, $(shell which podman))
	CONTAINER_RUNTIME ?= docker
else
	CONTAINER_RUNTIME ?= podman
endif

# Choose between docker-compose and podman-compose based on what is available
ifeq (, $(shell which podman-compose))
	COMPOSE_RUNTIME ?= docker-compose
else
	COMPOSE_RUNTIME ?= podman-compose
endif

ifeq ($(ENVIRONMENT),development)
	export ANSIBLE_AI_DATABASE_HOST := localhost
	export ANSIBLE_AI_DATABASE_NAME := wisdom
	export ANSIBLE_AI_DATABASE_PASSWORD := wisdom
	export ANSIBLE_AI_DATABASE_USER := wisdom
	export ARI_KB_PATH := ../ari/kb/
	export DJANGO_SETTINGS_MODULE := main.settings.development
	export ENABLE_ARI_POSTPROCESS := True
	export PYTHONUNBUFFERED := 1
	export SECRET_KEY := somesecret
	export DJANGO_SUPERUSER_PASSWORD := somesecret
	export SOCIAL_AUTH_OIDC_OIDC_ENDPOINT := https://sso.redhat.com/auth/realms/redhat-external
	export SOCIAL_AUTH_OIDC_KEY := ansible-wisdom-staging

	ifeq ($(wildcard $(PWD)/.env/.),)
		ifneq ($(wildcard $(PWD)/.env),)
			include $(PWD)/.env
		endif
	endif
endif

DEPRECATED:
	@echo
	@echo [WARN] This target has been deprecated. See Makefile for more information.
	@echo

# DEPRECATED: Please use build-wisdom-container instead
ansible-wisdom-container: build-wisdom-container DEPRECATED

.PHONY: build-wisdom-container
build-wisdom-container:
	${CONTAINER_RUNTIME} build -f wisdom-service.Containerfile -t ansible_wisdom .

# DEPRECATED: Please use run-server instead
run-django: run-server DEPRECATED

.PHONY: run-server
# Run Django application
run-server:
	python ansible_wisdom/manage.py runserver

# DEPRECATED: Please use run-server-containerized instead
run-django-container: run-server-containerized DEPRECATED

.PHONY: run-server-containerized
# Run Django application in container
run-server-containerized:
	${CONTAINER_RUNTIME} run -it --rm -p 8000:8000 --name ansible-wisdom localhost/ansible_wisdom

.PHONY: docker-compose
docker-compose:
	${COMPOSE_RUNTIME} -f tools/docker-compose/compose.yaml up --remove-orphans

# DEPRECATED: Please use start-backends instead
run-backends: start-backends DEPRECATED

.PHONY: start-backends
# Run backend services in container for running Django application from source
start-backends:
	${COMPOSE_RUNTIME} -f tools/docker-compose/compose-backends.yaml up --remove-orphans -d

.PHONY: stop-backends
# Stop backend services
stop-backends:
	${COMPOSE_RUNTIME} -f tools/docker-compose/compose-backends.yaml down

.PHONY: update-openapi-schema
# Update OpenAPI 3.0 schema while running the service in development env
update-openapi-schema:
	curl -X GET http://localhost:8000/api/schema/ -o tools/openapi-schema/ansible-wisdom-service.yaml

.PHONY: docker-compose-clean
docker-compose-clean:
	${COMPOSE_RUNTIME} -f tools/docker-compose/compose.yaml down

.PHONY: pip-compile
pip-compile:
	${COMPOSE_RUNTIME} -f tools/docker-compose/pip-compile.yaml up --remove-orphans

# DEPRECATED: Please use create-superuser-containerized instead
docker-create-superuser: create-superuser-containerized DEPRECATED

.PHONY: create-superuser-containerized
create-superuser-containerized:
	${CONTAINER_RUNTIME} exec -it docker-compose_django_1 wisdom-manage createsuperuser

.PHONY: migrate
migrate:
	python ansible_wisdom/manage.py migrate

.PHONY: create-cachetable
create-cachetable: migrate
	python ansible_wisdom/manage.py createcachetable

.PHONY: create-superuser
create-superuser: create-cachetable
	python ansible_wisdom/manage.py createsuperuser --noinput --username admin --email admin@example.com

.PHONY: create-application
create-application: create-superuser
	python ansible_wisdom/manage.py createapplication --name "Ansible Lightspeed for VS Code" --client-id Vu2gClkeR5qUJTUGHoFAePmBznd6RZjDdy5FW2wy  --redirect-uris "vscode://redhat.ansible"   public authorization-code

.PHONY: test
test:
	export MOCK_WCA_SECRETS_MANAGER=False && \
	python ansible_wisdom/manage.py test

.PHONY: code-coverage
# Run unit tests, calculate code coverage and display results in chrome
code-coverage:
	cd ansible_wisdom && \
	coverage erase && \
	coverage run --rcfile=../setup.cfg manage.py test && \
	coverage html && \
	google-chrome htmlcov/index.html

# ============================
# Admin Portal related commands
# ============================

# Compile and bundle Admin Portal into Django application
.PHONY: admin-portal-bundle
admin-portal-bundle:
	npm --prefix ./ansible_wisdom_console_react run build

# Run tests for Admin Portal
.PHONY: admin-portal-test
admin-portal-test:
	npm --prefix ./ansible_wisdom_console_react run test

# Run lint checks for Admin Portal
.PHONY: admin-portal-lint
admin-portal-lint:
	npm --prefix ./ansible_wisdom_console_react run lint
