# Example `ANSIBLE_AI_MODEL_MESH_CONFIG` configuration for `wca-dummy`

```json
{
    "ModelPipelineCompletions": {
        "provider": "wca-dummy",
        "config": {
            "inference_url": "http://localhost:8000"
        }
    },
    "ModelPipelineContentMatch": {
        "provider": "wca-dummy",
        "config": {
            "inference_url": "http://localhost:8000"
        }
    },
    "ModelPipelinePlaybookGeneration": {
        "provider": "wca-dummy",
        "config": {
            "inference_url": "http://localhost:8000"
        }
    },
    "ModelPipelineRoleGeneration": {
        "provider": "wca-dummy",
        "config": {
            "inference_url": "http://localhost:8000"
        }
    },
    "ModelPipelinePlaybookExplanation": {
        "provider": "wca-dummy",
        "config": {
            "inference_url": "http://localhost:8000"
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
