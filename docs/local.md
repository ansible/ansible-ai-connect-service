# Running locally

## Wisdom Service

```bash
git clone git@github.com:ansible/ansible-wisdom-service.git
cd ansible-wisdom-service
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e  .
set -o allexport && source ./.env && set +o allexport
python ansible_wisdom/manage.py createtoken --username testuser --password testuser --token-name testuser_token --create-user
python ansible_wisdom/manage.py runserver
```


`.env`

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

Download https://huggingface.co/jartine/Mistral-7B-Instruct-v0.2-llamafile/resolve/main/mistral-7b-instruct-v0.2.Q5_K_M.llamafile?download=true

```bash
chmod +x mistral-7b-instruct-v0.2.Q5_K_M.llamafile
./mistral-7b-instruct-v0.2.Q5_K_M.llamafile --host 127.0.0.1
```
