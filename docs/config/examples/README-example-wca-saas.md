# Example `ANSIBLE_AI_MODEL_MESH_CONFIG` configuration for `wca` (SaaS)

```json
{
    "ModelPipelineCompletions": {
        "provider": "wca",
        "config": {
            "inference_url": "https://api.dataplatform.test.cloud.ibm.com/",
            "api_key": "<api_key>",
            "model_id": "<model_id>",
            "verify_ssl": "True",
            "retry_count": "4",
            "health_check_api_key": "<api_key>",
            "health_check_model_id": "<model_id>",
            "idp_url": "<idp_url>",
            "idp_login": "<idp_login>",
            "idp_password": "<idp_password>",
            "one_click_default_api_key": "<api_key>",
            "one_click_default_model_id": "<model_id>",
            "enable_health_check": "True"
        }
    },
    "ModelPipelineContentMatch": {
        "provider": "wca",
        "config": {
            "inference_url": "https://api.dataplatform.test.cloud.ibm.com/",
            "api_key": "<api_key>",
            "model_id": "<model_id>",
            "verify_ssl": "True",
            "retry_count": "4",
            "health_check_api_key": "<api_key>",
            "health_check_model_id": "<model_id>",
            "idp_url": "<idp_url>",
            "idp_login": "<idp_login>",
            "idp_password": "<idp_password>",
            "one_click_default_api_key": "<api_key>",
            "one_click_default_model_id": "<model_id>"
        }
    },
    "ModelPipelinePlaybookGeneration": {
        "provider": "wca",
        "config": {
            "inference_url": "https://api.dataplatform.test.cloud.ibm.com/",
            "api_key": "<api_key>",
            "model_id": "<model_id>",
            "verify_ssl": "True",
            "retry_count": "4",
            "health_check_api_key": "<api_key>",
            "health_check_model_id": "<model_id>",
            "idp_url": "<idp_url>",
            "idp_login": "<idp_login>",
            "idp_password": "<idp_password>",
            "one_click_default_api_key": "<api_key>",
            "one_click_default_model_id": "<model_id>4"
        }
    },
    "ModelPipelineRoleGeneration": {
        "provider": "wca",
        "config": {
            "inference_url": "https://api.dataplatform.test.cloud.ibm.com/",
            "api_key": "<api_key>",
            "model_id": "<model_id>",
            "verify_ssl": "True",
            "retry_count": "4",
            "health_check_api_key": "<api_key>",
            "health_check_model_id": "<model_id>",
            "idp_url": "<idp_url>",
            "idp_login": "<idp_login>",
            "idp_password": "<idp_password>",
            "one_click_default_api_key": "<api_key>",
            "one_click_default_model_id": "<model_id>"
        }
    },
    "ModelPipelinePlaybookExplanation": {
        "provider": "wca",
        "config": {
            "inference_url": "https://api.dataplatform.test.cloud.ibm.com/",
            "api_key": "<api_key>",
            "model_id": "<model_id>",
            "verify_ssl": "True",
            "retry_count": "4",
            "health_check_api_key": "<api_key>",
            "health_check_model_id": "<model_id>",
            "idp_url": "<idp_url>",
            "idp_login": "<idp_login>",
            "idp_password": "<idp_password>",
            "one_click_default_api_key": "<api_key>",
            "one_click_default_model_id": "<model_id>"
        }
    },
    "ModelPipelineRoleExplanation": {
        "provider": "wca",
        "config": {
            "inference_url": "https://api.dataplatform.test.cloud.ibm.com/",
            "api_key": "<api_key>",
            "model_id": "<model_id>",
            "verify_ssl": "True",
            "retry_count": "4",
            "health_check_api_key": "<api_key>",
            "health_check_model_id": "<model_id>",
            "idp_url": "<idp_url>",
            "idp_login": "<idp_login>",
            "idp_password": "<idp_password>",
            "one_click_default_api_key": "<api_key>",
            "one_click_default_model_id": "<model_id>"
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
