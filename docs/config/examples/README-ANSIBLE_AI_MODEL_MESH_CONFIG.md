# Example `ANSIBLE_AI_MODEL_MESH_CONFIG` configuration

`ANSIBLE_AI_MODEL_MESH_CONFIG` can be defined with either JSON or YAML.

## JSON Configuration

```json
{
    "ModelPipelineCompletions": {
        "provider": "ollama",
        "config": {
            "inference_url": "http://host.containers.internal:11434",
            "model_id": "mistral:instruct"
        }
    },
    "ModelPipelineContentMatch": {
        "provider": "ollama",
        "config": {
            "inference_url": "http://host.containers.internal:11434",
            "model_id": "mistral:instruct"
        }
    },
    "ModelPipelinePlaybookGeneration": {
        "provider": "ollama",
        "config": {
            "inference_url": "http://host.containers.internal:11434",
            "model_id": "mistral:instruct"
        }
    },
    "ModelPipelineRoleGeneration": {
        "provider": "ollama",
        "config": {
            "inference_url": "http://host.containers.internal:11434",
            "model_id": "mistral:instruct"
        }
    },
    "ModelPipelinePlaybookExplanation": {
        "provider": "ollama",
        "config": {
            "inference_url": "http://host.containers.internal:11434",
            "model_id": "mistral:instruct"
        }
    },
    "ModelPipelineChatBot": {
        "provider": "http",
        "config": {
            "inference_url": "http://localhost:8000",
            "model_id": "granite3-8b"
        }
    }
}
```

## YAML Configuration

```yaml
MetaData:
  provider: ollama
  config:
    inference_url: http://localhost
    model_id: a-model-id
ModelPipelineCompletions:
  provider: ollama
  config:
    inference_url: http://localhost
    model_id: a-model-id
ModelPipelinePlaybookGeneration:
  provider: ollama
  config:
    inference_url: http://localhost
    model_id: a-model-id
ModelPipelineRoleGeneration:
  provider: ollama
  config:
    inference_url: http://localhost
    model_id: a-model-id
ModelPipelinePlaybookExplanation:
  provider: ollama
  config:
    inference_url: http://localhost
    model_id: a-model-id
ModelPipelineChatBot:
  provider: http,
  config:
    inference_url: http://localhost
    model_id: granite3-8b
```
