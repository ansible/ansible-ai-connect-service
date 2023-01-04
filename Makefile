MODEL_PATH ?= ${PWD}/model/wisdom
CONTAINER_RUNTIME ?= podman
ENVIRONMENT ?= development

model-archive:
	torch-model-archiver -f \
	--model-name=wisdom \
	--version=1.0 \
	--serialized-file=${MODEL_PATH}/pytorch_model.bin \
	--handler=./torchserve/handler.py \
	--extra-files "${MODEL_PATH}/added_tokens.json,${MODEL_PATH}/config.json,${MODEL_PATH}/merges.txt,${MODEL_PATH}/pytorch_model.bin,${MODEL_PATH}/special_tokens_map.json,${MODEL_PATH}/tokenizer.json,${MODEL_PATH}/tokenizer_config.json,${MODEL_PATH}/training_flags.json,${MODEL_PATH}/vocab.json,./torchserve/tokenizer.py" \
	--export-path=${MODEL_PATH}

container:
	${CONTAINER_RUNTIME} build --target ${ENVIRONMENT} -t wisdom:latest .

run-model-server-container:
	@if [ "${ENVIRONMENT}" != "production" ]; then\
		${CONTAINER_RUNTIME} run -it --gpus all --rm -p 7080:7080 -v ${MODEL_PATH}/wisdom.mar:/home/model-server/model-store/wisdom.mar --name=wisdom wisdom:latest;\
	else\
		${CONTAINER_RUNTIME} run -it --gpus all --rm -p 7080:7080 --name=wisdom wisdom:latest;\
	fi

run-model-server:
	torchserve --start --ts-config=./config.properties --models wisdom=wisdom.mar --model-store ./model/wisdom

stop-model-server:
	torchserve --stop

clean:
	rm ${MODEL_PATH}/wisdom.mar
