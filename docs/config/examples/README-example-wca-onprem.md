# Example `ANSIBLE_AI_MODEL_MESH_CONFIG` configuration for `wca-onprem`

```json
{
    "ModelPipelineCompletions": {
        "provider": "wca-onprem",
        "config": {
            "inference_url": "<ibm-cpd-url>",
            "api_key": "<api_key>",
            "model_id": "<model_id>",
            "verify_ssl": "True",
            "retry_count": "4",
            "health_check_api_key": "<api_key>",
            "health_check_model_id": "<model_id>",
            "username": "<username>",
            "enable_health_check": "True"
        }
    },
    "ModelPipelineContentMatch": {
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
    "ModelPipelineRoleGeneration": {
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
    "ModelPipelinePlaybookExplanation": {
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
    "ModelPipelineRoleExplanation": {
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
