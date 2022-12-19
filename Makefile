MODEL_PATH ?= ./model/wisdom
CONTAINER_RUNTIME ?= podman
DOCKER_VOLUME_PATH ?= ${PWD}/model
ENVIRONMENT ?= development

model-archive:
	python -m venv .venv
	(source .venv/bin/activate)
	pip install -r requirements-dev.txt
	torch-model-archiver -f \
	--model-name=wisdom \
	--version=1.0 \
	--serialized-file=${MODEL_PATH}/pytorch_model.bin \
	--handler=./torchserve/handler.py \
	--extra-files "${MODEL_PATH}/added_tokens.json,${MODEL_PATH}/config.json,${MODEL_PATH}/merges.txt,${MODEL_PATH}/pytorch_model.bin,${MODEL_PATH}/special_tokens_map.json,${MODEL_PATH}/tokenizer.json,${MODEL_PATH}/tokenizer_config.json,${MODEL_PATH}/training_flags.json,${MODEL_PATH}/vocab.json,./torchserve/tokenizer.py" \
	--export-path=${MODEL_PATH}

container:
	${CONTAINER_RUNTIME} build --target ${ENVIRONMENT} -t wisdom:latest .

run-server:
	${CONTAINER_RUNTIME} run -it --gpus all --rm -p 7080:7080 -v ${DOCKER_VOLUME_PATH}:/home/model-server/model-store --name=wisdom wisdom:latest

clean:
	rm ${MODEL_PATH}/wisdom.mar
