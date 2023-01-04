MODEL_PATH ?= ${PWD}/model/wisdom
CONTAINER_RUNTIME ?= podman
ENVIRONMENT ?= development
TAG=latest

model-archive:
	python -m venv .venv
	.venv/bin/pip install -r requirements-dev.txt
	.venv/bin/torch-model-archiver -f \
	--model-name=wisdom \
	--version=1.0 \
	--serialized-file=${MODEL_PATH}/pytorch_model.bin \
	--handler=./torchserve/handler.py \
	--extra-files "${MODEL_PATH}/added_tokens.json,${MODEL_PATH}/config.json,${MODEL_PATH}/merges.txt,${MODEL_PATH}/pytorch_model.bin,${MODEL_PATH}/special_tokens_map.json,${MODEL_PATH}/tokenizer.json,${MODEL_PATH}/tokenizer_config.json,${MODEL_PATH}/training_flags.json,${MODEL_PATH}/vocab.json,./torchserve/tokenizer.py" \
	--export-path=${MODEL_PATH}

model-container:
	${CONTAINER_RUNTIME} build --target ${ENVIRONMENT} -t wisdom:${TAG} .

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

clean:
	rm ${MODEL_PATH}/wisdom.mar
