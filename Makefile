MODEL_PATH ?= ${PWD}/model/wisdom
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

model-archive:
	python3 -m venv .venv
	.venv/bin/pip3 install -r requirements-dev.txt
	.venv/bin/torch-model-archiver -f \
	--model-name=wisdom \
	--version=1.0 \
	--serialized-file=${MODEL_PATH}/pytorch_model.bin \
	--handler=./torchserve/handler.py \
	--extra-files "${MODEL_PATH}/added_tokens.json,${MODEL_PATH}/config.json,${MODEL_PATH}/merges.txt,${MODEL_PATH}/pytorch_model.bin,${MODEL_PATH}/special_tokens_map.json,${MODEL_PATH}/tokenizer.json,${MODEL_PATH}/tokenizer_config.json,${MODEL_PATH}/training_flags.json,${MODEL_PATH}/vocab.json,./torchserve/tokenizer.py" \
	--export-path=${MODEL_PATH}

model-container:
	${CONTAINER_RUNTIME} build --target ${ENVIRONMENT} -f wisdom-model-server.Containerfile -t wisdom:${TAG} .

ansible-wisdom-container:
	${CONTAINER_RUNTIME} build -f wisdom-service.Containerfile -t ansible_wisdom .

# Start torchserve container
run-model-server:
	@if [ "${ENVIRONMENT}" != "production" ]; then\
		${CONTAINER_RUNTIME} run -it --gpus all --rm -p 7080:7080 -v ${MODEL_PATH}/wisdom.mar:/home/model-server/model-store/wisdom.mar --name=wisdom wisdom:${TAG};\
	else\
		${CONTAINER_RUNTIME} run -it --gpus all --rm -p 7080:7080 ${SECURITY_OPT} --name=wisdom wisdom:${TAG};\
	fi

# Run Django application
run-django:
	python ansible_wisdom/manage.py runserver

run-django-container:
	${CONTAINER_RUNTIME} run -it --rm -p 8000:8000 --name ansible-wisdom localhost/ansible_wisdom

docker-compose:
	${COMPOSE_RUNTIME} -f tools/docker-compose/compose.yaml up --remove-orphans

clean:
	rm ${MODEL_PATH}/wisdom.mar
