model-archive:
	python -m venv .venv
	(source .venv/bin/activate)
	pip install -r requirements-dev.txt
	torch-model-archiver -f \
  	--model-name=wisdom \
  	--version=1.0 \
  	--serialized-file=./model/wisdom/pytorch_model.bin \
  	--handler=./ansible_wisdom/model/handler.py \
  	--extra-files "./model/wisdom/added_tokens.json,./model/wisdom/config.json,./model/wisdom/merges.txt,./model/wisdom/pytorch_model.bin,./model/wisdom/special_tokens_map.json,./model/wisdom/tokenizer.json,./model/wisdom/tokenizer_config.json,./model/wisdom/training_flags.json,./model/wisdom/vocab.json,./ansible_wisdom/model/tokenizer.py" \
  	--export-path=./model/

container:
	podman build -t wisdom:latest .

run-server:
	podman run -it --rm -p 7080:7080 --name=wisdom wisdom:latest
