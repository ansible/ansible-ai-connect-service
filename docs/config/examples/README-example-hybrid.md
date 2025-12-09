# Example _hybrid_ `ANSIBLE_AI_MODEL_MESH_CONFIG` configuration

Separating the configuration for each pipeline allows different settings to be used for each; or disabled all together.

For example the following configuration uses `ollama` for "Completions" however `wca-onprem` for "Playbook Generation". "ContentMatches", "Playbook Explanation" and "Role Generation" are not configured and would fall back to a "No Operation" implementation. The "Chat Bot" uses a plain `http` implementation to another service.

```json
{
    "ModelPipelineCompletions": {
        "provider": "ollama",
        "config": {
            "inference_url": "http://localhost:8000",
            "model_id": "ollama-model"
        }
    },
    "ModelPipelinePlaybookGeneration": {
        "provider": "wca-onprem",
        "config": {
            "inference_url": "<ibm-cpd-url>",
            "api_key": "<api_key>",
            "model_id": "<model_id>",
            "verify_ssl": "True",
            "retry_count": "4",
            "health_check_api_key": "<api_key>",
            "health_check_model_id": "<model_id>",
            "username": "<username>"
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
