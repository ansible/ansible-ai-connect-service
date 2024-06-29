- [Running locally](#running-locally)
  - [Database](#database)
  - [Wisdom Service](#wisdom-service)
  - [Model Server](#model-server)
    - [Mistral-7B-Instruct](#mistral-7b-instruct)
    - [TinyLlama-1.1B](#tinyllama-11b)


# Running locally

To run the code generation service (note: content match not included yet) on your laptop.


## Database

You can set up a postgres server by running `docker compose` or the `make`
```bash
make start-backends
```


## Wisdom Service

```bash
git clone git@github.com:ansible/ansible-wisdom-service.git
cd ansible-wisdom-service
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e  .
set -o allexport && source ./.env && set +o allexport
python ansible_wisdom/manage.py migrate --noinput
python ansible_wisdom/manage.py createcachetable
python ansible_wisdom/manage.py collectstatic --noinput
python ansible_wisdom/manage.py createtoken --username testuser --password testuser --token-name testuser_token --create-user
python ansible_wisdom/manage.py runserver
```


A sample `.env` file.  Adjust them according to your actual setup, e.g. the postgres server info.

```bash
DEPLOYMENT_MODE=upstream
ANSIBLE_AI_DATABASE_HOST=localhost
ANSIBLE_AI_DATABASE_PORT=5432
ANSIBLE_AI_DATABASE_NAME=wisdom
ANSIBLE_AI_DATABASE_PASSWORD=wisdom
ANSIBLE_AI_DATABASE_USER=wisdom
DJANGO_SETTINGS_MODULE=main.settings.development
ENABLE_ARI_POSTPROCESS=False
PYTHONUNBUFFERED=1
SECRET_KEY=somesecret
# llama server
ANSIBLE_AI_MODEL_MESH_HOST=http://127.0.0.1
ANSIBLE_AI_MODEL_MESH_INFERENCE_PORT=8080
ANSIBLE_AI_MODEL_MESH_API_TYPE=llamacpp
ANSIBLE_AI_MODEL_NAME=mistral-7b-instruct-v0.1.Q4_K_M.gguf

DEBUG=True
ANSIBLE_WISDOM_DOMAIN=*
LAUNCHDARKLY_SDK_KEY=flagdata.json
```

## Model Server

### Mistral-7B-Instruct

Download https://huggingface.co/jartine/Mistral-7B-Instruct-v0.2-llamafile/resolve/main/mistral-7b-instruct-v0.2.Q5_K_M.llamafile?download=true

```bash
chmod +x mistral-7b-instruct-v0.2.Q5_K_M.llamafile
./mistral-7b-instruct-v0.2.Q5_K_M.llamafile --host 127.0.0.1
```

### TinyLlama-1.1B

The Tiny Llama would work as well

Download https://huggingface.co/jartine/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/TinyLlama-1.1B-Chat-v1.0.Q5_K_M.llamafile?download=true


```bash
chmod +x ./TinyLlama-1.1B-Chat-v1.0.Q5_K_M.llamafile
./TinyLlama-1.1B-Chat-v1.0.Q5_K_M.llamafile --host 127.0.0.1
```
