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
	${COMPOSE_RUNTIME} -f tools/docker-compose/compose.yaml up --remove-orphans --detach
	@until $$(curl -sfo /dev/null http://localhost:8000); do printf '.'; sleep 5; done
	@printf '\nDjango Server is up and running.\n'
	@sleep 3
	@printf 'Kill Django server...\n'
	${CONTAINER_RUNTIME} kill docker-compose_django_1
	@sleep 3
	${CONTAINER_RUNTIME} ps -a

# Stop backend services
stop-backends:
	${COMPOSE_RUNTIME} -f tools/docker-compose/compose.yaml down
	@sleep 3
	${CONTAINER_RUNTIME} ps -a
