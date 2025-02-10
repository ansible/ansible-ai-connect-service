# Example `ANSIBLE_AI_MODEL_MESH_CONFIG` configuration for `dummy`

```json
{
    "ModelPipelineCompletions": {
        "provider": "dummy",
        "config": {
            "inference_url": "http://localhost:8000",
            "body": "{\"predictions\":[\"ansible.builtin.apt:\\n  name: nginx\\n  update_cache: true\\n  state: present\\n\"]}",
            "latency_max_msec": "3000",
            "latency_use_jitter": "False"
        }
    },
    "ModelPipelineContentMatch": {
        "provider": "dummy",
        "config": {
            "inference_url": "http://localhost:8000",
            "body": "{\"predictions\":[\"ansible.builtin.apt:\\n  name: nginx\\n  update_cache: true\\n  state: present\\n\"]}",
            "latency_max_msec": "3000",
            "latency_use_jitter": "False"
        }
    },
    "ModelPipelinePlaybookGeneration": {
        "provider": "dummy",
        "config": {
            "inference_url": "http://localhost:8000",
            "body": "{\"predictions\":[\"ansible.builtin.apt:\\n  name: nginx\\n  update_cache: true\\n  state: present\\n\"]}",
            "latency_max_msec": "3000",
            "latency_use_jitter": "False"
        }
    },
    "ModelPipelineRoleGeneration": {
        "provider": "dummy",
        "config": {
            "inference_url": "http://localhost:8000",
            "body": "{\"predictions\":[\"ansible.builtin.apt:\\n  name: nginx\\n  update_cache: true\\n  state: present\\n\"]}",
            "latency_max_msec": "3000",
            "latency_use_jitter": "False"
        }
    },
    "ModelPipelinePlaybookExplanation": {
        "provider": "dummy",
        "config": {
            "inference_url": "http://localhost:8000",
            "body": "{\"predictions\":[\"ansible.builtin.apt:\\n  name: nginx\\n  update_cache: true\\n  state: present\\n\"]}",
            "latency_max_msec": "3000",
            "latency_use_jitter": "False"
        }
    },
    "ModelPipelineRoleExplanation": {
        "provider": "dummy",
        "config": {
            "inference_url": "http://localhost:8000",
            "body": "{\"predictions\":[\"ansible.builtin.apt:\\n  name: nginx\\n  update_cache: true\\n  state: present\\n\"]}",
            "latency_max_msec": "3000",
            "latency_use_jitter": "False"
        }
    },
    "ModelPipelineChatBot": {
        "provider": "http",
        "config": {
            "inference_url": "<CHATBOT_URL>",
            "model_id": "<CHATBOT_DEFAULT_MODEL>"
        }
    }
}
```
