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

.PHONY: ansible-wisdom-container run-django run-django-container docker-compose

ansible-wisdom-container:
	${CONTAINER_RUNTIME} build -f wisdom-service.Containerfile -t ansible_wisdom .

# Run Django application
run-django:
	python ansible_wisdom/manage.py runserver

run-django-container:
	${CONTAINER_RUNTIME} run -it --rm -p 8000:8000 --name ansible-wisdom localhost/ansible_wisdom

docker-compose:
	${COMPOSE_RUNTIME} -f tools/docker-compose/compose.yaml up --remove-orphans

# Run backend services in container for running Django application from source
run-backends:
	${COMPOSE_RUNTIME} -f tools/docker-compose/compose-backends.yaml up --remove-orphans

# Stop backend services
stop-backends:
	${COMPOSE_RUNTIME} -f tools/docker-compose/compose-backends.yaml down

# Update OpenAPI 3.0 schema while running the service in development env
update-openapi-schema:
	curl -X GET http://localhost:8000/api/schema/ -o tools/openapi-schema/ansible-wisdom-service.yaml

docker-compose-clean:
	${COMPOSE_RUNTIME} -f tools/docker-compose/compose.yaml down

docker-create-superuser:
	${CONTAINER_RUNTIME} exec -it docker-compose_django_1 wisdom-manage createsuperuser

# Run unit tests, calculate code coverage and display results in chrome
code-coverage: export SHELL=/bin/bash # for using source
code-coverage:
	set -o allexport && source _env &&\
	cd ansible_wisdom && \
	coverage erase && \
	coverage run --rcfile=../setup.cfg manage.py test && \
	coverage html && \
	google-chrome htmlcov/index.html

# Initialize local Django DB by running migration and creating a superuser
init-db: export SHELL=/bin/bash # for using source
init-db:
	set -o allexport && source _env && venv/bin/python ansible_wisdom/manage.py migrate
	set -o allexport && source _env && echo "from django.contrib.auth import get_user_model;"\
	"User = get_user_model();"\
	"User.objects.create_superuser('admin', 'admin@example.com', '$${SECRET_KEY}')"\
	| venv/bin/python3 ansible_wisdom/manage.py shell
