MODEL_PATH ?= ./model/wisdom

model-archive:
	python -m venv .venv
	(source .venv/bin/activate)
	pip install -r requirements-dev.txt
	torch-model-archiver -f \
	--model-name=wisdom \
	--version=1.0 \
	--serialized-file=${MODEL_PATH}/pytorch_model.bin \
	--handler=./torchserve/handler.py \
	--extra-files "${MODEL_PATH}/added_tokens.json,${MODEL_PATH}/config.json,${MODEL_PATH}/merges.txt,${MODEL_PATH}/pytorch_model.bin,${MODEL_PATH}/special_tokens_map.json,${MODEL_PATH}/tokenizer.json,${MODEL_PATH}/tokenizer_config.json,${MODEL_PATH}/training_flags.json,${MODEL_PATH}/vocab.json,./ansible_wisdom/ai/api/ansible/tokenizer.py" \
	--export-path=${MODEL_PATH}

container:
	podman build -t wisdom:latest .

run-server:
	podman run -it --rm -p 7080:7080 --name=wisdom wisdom:latest

clean:
	rm ${MODEL_PATH}/wisdom.mar
