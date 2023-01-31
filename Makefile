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
