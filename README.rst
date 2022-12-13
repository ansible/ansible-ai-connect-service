
# Ansible Wisdom service

Note: This repository is under active development and is not yet ready for production use.


##  Running server locally

### Host

1. Install all the dependencies using
```
pip install -r requirements.txt
```

2. Copy the latest checkpoint under `.checkpoint/latest` directory within
the root folder of the project, alternatively, edit the variable `ANSIBLE_WISDOM_AI_CHECKPOINT_PATH` in `ansible_wisdom/main/settings/development.py` file to point to the checkpoint location on disk.

2. Run the server using
```
cd ansible_wisdom
HF_DATASETS_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python manage.py runserver
```

4. this will start the application at `http://127.0.0.1:8000/`

### Container

1. Specify the model location (default is `./model/wisdom`)
```
export MODEL_PATH=./model/wisdom
```
2. Generate the model archive
```
make mode-archive
```
3. Build the container image
```
make container
```
to produce a production container:
```
ENVIRONMENT=production make container
```
4. Run the server in dev mode
```
make run-server
```

## Posting a request

Post a request using curl

```
curl -X 'POST' \
  'http://127.0.0.1:8000/api/completions/' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  		"context": "---\n- hosts: all\n  tasks:\n  - name: Install nginx and nodejs 12 Packages\n", "prompt": "Install nginx and nodejs 12 Packages"
    }'
```

## Test cases
Work in progress

## TODO
-
