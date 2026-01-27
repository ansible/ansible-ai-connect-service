# DNM
ENVIRONMENT ?= development
TAG ?= latest
ANSIBLE_AI_PROJECT_NAME ?= Ansible AI Connect

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
	export DJANGO_SETTINGS_MODULE := ansible_ai_connect.main.settings.development
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
	wisdom-manage runserver

# DEPRECATED: Please use run-server-containerized instead
run-django-container: run-server-containerized DEPRECATED

.PHONY: run-server-containerized
# Run Django application in container
run-server-containerized:
	${CONTAINER_RUNTIME} run -it --rm -p 8000:8000 --name ansible-wisdom localhost/ansible_wisdom

.PHONY: docker-compose
docker-compose:
	${COMPOSE_RUNTIME} -f ${PWD}/tools/docker-compose/compose.yaml up --remove-orphans

.PHONY: start-db
# Run db in container for running Django application from source
start-db:
	${COMPOSE_RUNTIME} -f ${PWD}/tools/docker-compose/compose-db.yaml up --remove-orphans -d

.PHONY: stop-db
# stop db container
stop-db:
	${COMPOSE_RUNTIME} -f ${PWD}/tools/docker-compose/compose-db.yaml down

.PHONY: start-backends
# Run backend services in container for running Django application from source
start-backends:
	${COMPOSE_RUNTIME} -f ${PWD}/tools/docker-compose/compose-db.yaml -f ${PWD}/tools/docker-compose/compose-prom-grafana.yaml up --remove-orphans -d

.PHONY: stop-backends
# Stop backend services
stop-backends:
	${COMPOSE_RUNTIME} -f ${PWD}/tools/docker-compose/compose-db.yaml -f ${PWD}/tools/docker-compose/compose-prom-grafana.yaml down

.PHONY: update-openapi-schema
# Update OpenAPI 3.0 schema while running the service in development env
update-openapi-schema:
	curl -X GET http://localhost:8000/api/schema/ -o tools/openapi-schema/ansible-ai-connect-service.yaml
	curl -w "\n" -X GET "http://localhost:8000/api/schema/?format=json" > tools/openapi-schema/ansible-ai-connect-service.json

.PHONY: validate-openapi-schema
# Validate OpenAPI schema against OpenAPI 3.0 specification (requires server to be running)
validate-openapi-schema:
	@echo "Validating OpenAPI schema at http://localhost:8000/api/schema/ ..."
	@python3 -c "from openapi_spec_validator import validate_url; from openapi_spec_validator.validation.validators import OpenAPIV30SpecValidator; validate_url('http://localhost:8000/api/schema/', cls=OpenAPIV30SpecValidator); print('✓ OpenAPI schema is valid!')"

.PHONY: docker-compose-clean
docker-compose-clean:
	${COMPOSE_RUNTIME} -f ${PWD}/tools/docker-compose/compose.yaml down

.PHONY: export
export:
	${CONTAINER_RUNTIME} run --os linux \
		--volume $(PWD):/var/www/wisdom:Z \
		--workdir /var/www/wisdom \
		registry.access.redhat.com/ubi9/ubi:latest \
		/var/www/wisdom/tools/scripts/uv-export.sh

# DEPRECATED: Please use create-superuser-containerized instead
docker-create-superuser: create-superuser-containerized DEPRECATED

.PHONY: create-superuser-containerized
create-superuser-containerized:
	${CONTAINER_RUNTIME} exec -it docker-compose_django_1 wisdom-manage createsuperuser

.PHONY: migrate
migrate:
	wisdom-manage migrate

.PHONY: makemigrations
makemigrations:
	wisdom-manage makemigrations

.PHONY: create-cachetable
create-cachetable: migrate
	wisdom-manage createcachetable

.PHONY: create-superuser
create-superuser: create-cachetable
	wisdom-manage createsuperuser --noinput --username admin --email admin@example.com

.PHONY: create-testuser
create-testuser: create-superuser
	wisdom-manage createtoken --username testuser --password testuser --token-name testuser_token --create-user

.PHONY: create-application
create-application: create-testuser
	wisdom-manage createapplication --name "${ANSIBLE_AI_PROJECT_NAME} for VS Code" --client-id Vu2gClkeR5qUJTUGHoFAePmBznd6RZjDdy5FW2wy  --redirect-uris "vscode://redhat.ansible"   public authorization-code

.PHONY: test
test:
	export MOCK_WCA_SECRETS_MANAGER=False && \
	wisdom-manage test $$WISDOM_TEST

.PHONY: code-coverage
# Run unit tests, calculate code coverage and display results in chrome
code-coverage:
	coverage erase && \
	coverage run --rcfile=setup.cfg -m ansible_ai_connect.manage test ansible_ai_connect && \
	coverage html && \
	google-chrome htmlcov/index.html

# ============================
# Admin Portal related commands
# ============================

# Compile and bundle Admin Portal into Django application
.PHONY: admin-portal-bundle
admin-portal-bundle:
	npm --prefix ./ansible_ai_connect_admin_portal run build

# Run tests for Admin Portal
.PHONY: admin-portal-test
admin-portal-test:
	npm --prefix ./ansible_ai_connect_admin_portal run test

# Run lint checks for Admin Portal
.PHONY: admin-portal-lint
admin-portal-lint:
	npm --prefix ./ansible_ai_connect_admin_portal run lint

# ============================
# Chatbot UI related commands
# ============================

# Compile and bundle Chatbot UI into Django application
.PHONY: chatbot-bundle
chatbot-bundle:
	npm --prefix ./ansible_ai_connect_chatbot run build

# Run tests for Chatbot UI with code coverage
.PHONY: chatbot-test
chatbot-test:
	npm --prefix ./ansible_ai_connect_chatbot run coverage

# Run lint checks for Admin Portal
.PHONY: chatbot-lint
chatbot-lint:
	npm --prefix ./ansible_ai_connect_chatbot run eslint

pre-commit:
	pre-commit run --color=always --all-files
