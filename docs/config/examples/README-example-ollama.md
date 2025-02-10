# Example `ANSIBLE_AI_MODEL_MESH_CONFIG` configuration for `ollama`

```json
{
    "ModelPipelineCompletions": {
        "provider": "ollama",
        "config": {
            "inference_url": "http://localhost:8000",
            "model_id": "ollama-model"
        }
    },
    "ModelPipelineContentMatch": {
        "provider": "ollama",
        "config": {
            "inference_url": "http://localhost:8000",
            "model_id": "ollama-model"
        }
    },
    "ModelPipelinePlaybookGeneration": {
        "provider": "ollama",
        "config": {
            "inference_url": "http://localhost:8000",
            "model_id": "ollama-model"
        }
    },
    "ModelPipelineRoleGeneration": {
        "provider": "ollama",
        "config": {
            "inference_url": "http://localhost:8000",
            "model_id": "ollama-model"
        }
    },
    "ModelPipelinePlaybookExplanation": {
        "provider": "ollama",
        "config": {
            "inference_url": "http://localhost:8000",
            "model_id": "ollama-model"
        }
    },
    "ModelPipelineRoleExplanation": {
        "provider": "ollama",
        "config": {
            "inference_url": "http://localhost:8000",
            "model_id": "ollama-model"
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
