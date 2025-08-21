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
    "ModelPipelineRoleExplanation": {
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
ModelPipelineRoleExplanation:
  provider: ollama
  config:
    inference_url: http://localhost
    model_id: a-model-id
ModelPipelineChatBot:
  provider: http
  config:
    inference_url: http://localhost
    model_id: granite3-8b
```

# HTTP Pipeline SSL Configuration

This document explains SSL verification configuration for HTTP pipelines in the Ansible AI Connect Service.

## SSL Verification Options

The HTTP pipeline supports two SSL configuration options:

- `verify_ssl`: Boolean flag to enable/disable SSL certificate verification (default: `true`)
- `ca_cert_file`: Optional path to a custom CA certificate file

## Configuration Precedence

**Important**: When both options are configured, `ca_cert_file` takes precedence over `verify_ssl`.

The SSL verification behavior follows this priority:

1. **If `ca_cert_file` is provided** (not null/empty): Use the specified CA certificate file for SSL verification
2. **If `ca_cert_file` is not provided** (null/empty): Use the `verify_ssl` boolean value

## Configuration Examples

### Using Custom CA Certificate (OpenShift Service Account)

```json
{
    "ModelPipelineChatBot": {
        "provider": "http",
        "config": {
            "inference_url": "https://ls-stack-service.wisdom-ls-stack.svc.cluster.local:8443",
            "model_id": "granite3-8b",
            "verify_ssl": true,
            "ca_cert_file": "/var/run/secrets/kubernetes.io/serviceaccount/service-ca.crt"
        }
    }
}
```

In this example, SSL verification will use the OpenShift Service Account CA certificate file, regardless of the `verify_ssl` setting.

### Using Default SSL Verification

```json
{
    "ModelPipelineChatBot": {
        "provider": "http",
        "config": {
            "inference_url": "https://api.example.com:8443",
            "model_id": "granite3-8b",
            "verify_ssl": true
        }
    }
}
```

In this example, SSL verification will use the system's default CA bundle since no `ca_cert_file` is specified.

### Disabling SSL Verification

```json
{
    "ModelPipelineChatBot": {
        "provider": "http",
        "config": {
            "inference_url": "https://internal-service:8443",
            "model_id": "granite3-8b",
            "verify_ssl": false
        }
    }
}
```

In this example, SSL verification is disabled since no `ca_cert_file` is provided and `verify_ssl` is `false`.

## Use Cases

- **OpenShift/Kubernetes environments**: Use `ca_cert_file` to specify the service account CA certificate
- **Internal services with custom certificates**: Use `ca_cert_file` to specify the internal CA certificate
- **Development/testing**: Use `verify_ssl: false` to disable SSL verification
- **Public services**: Use `verify_ssl: true` with system default CA bundle
