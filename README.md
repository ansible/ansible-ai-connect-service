# Ansible Wisdom service

Note: This repository is under active development and is not yet ready for production use.

## Running server locally

### Host

1. Clone the repository and install all the dependencies using

```bash
pip install -r requirements.txt
```

2. Run the server using

- Copy the model in `MODEL_PATH` folder and start the model mesh server

```bash
# Using container
```bash
export MODEL_PATH=./model/wisdom
make mode-archive
make container
make run-server
```

3. Test if the model mesh server is running
:information_source: A tunnel from localhost:7080 to remote-container-host:7080 is required when using podman-remote.

Request:

```bash
curl -X 'POST' \
  'http://127.0.0.1:7080/predictions/wisdom/' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
        "instances":[{"context": "---\n- hosts: all\n  tasks:\n  - name: Install nginx and nodejs 12 Packages\n", "prompt": "Install nginx and nodejs 12 Packages"}]
    }'
```

Response:

```json
{
  "predictions": [
    "- name: ansible Convert instance config dict to a list\n      set_fact:\n        ansible_list: \"{{ instance_config_dict.results | map(attribute='ansible_facts.instance_conf_dict') | list }}\"\n      when: server.changed | bool\n"
  ]
}
```

4. Run the `ansible-wisdom-api` server

- Update the `ANSIBLE_AI_MODEL_MESH_HOST` in `ansible_wisdom/main/settings/development.py` file to point to the model mesh server.

- Run the server

```bash
cd ansible_wisdom
python manage.py runserver
```

- This will start the application at `http://127.0.0.1:8000/`

5. Test the server

Request:

```bash
# Post a request using curl
curl -X 'POST' \
  'http://127.0.0.1:8000/api/ai/completions/' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
    "context": "---\n- hosts: all\n  tasks:\n  - name: Install nginx and nodejs 12 Packages\n", "prompt": "Install nginx and nodejs 12 Packages"
    }'
```

Response:

```json
{
    "predictions": [
        "- name: Install nginx and nodejs 12 Packages\n  apt:\n    name:\n      - nginx\n      - nodejs\n    state: latest\n"
    ]
}
```

### Container

## Test cases

Work in progress

## TODO

-
