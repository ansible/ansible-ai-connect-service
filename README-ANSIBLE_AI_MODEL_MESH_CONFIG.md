# Example `ANSIBLE_AI_MODEL_MESH_CONFIG` configuration

Pay close attention to the formatting of the blocks.

Each ends with `}},` otherwise conversion of the multi-line setting to a `str` can fail.

```text
ANSIBLE_AI_MODEL_MESH_CONFIG="{
    "ModelPipelineCompletions": {
        "provider": "ollama",
        "config": {
            "inference_url": "http://host.containers.internal:11434",
            "model_id": "mistral:instruct"}},
    "ModelPipelineContentMatch": {
        "provider": "ollama",
        "config": {
            "inference_url": "http://host.containers.internal:11434",
            "model_id": "mistral:instruct"}},
    "ModelPipelinePlaybookGeneration": {
        "provider": "ollama",
        "config": {
            "inference_url": "http://host.containers.internal:11434",
            "model_id": "mistral:instruct"}},
    "ModelPipelineRoleGeneration": {
        "provider": "ollama",
        "config": {
            "inference_url": "http://host.containers.internal:11434",
            "model_id": "mistral:instruct"}},
    "ModelPipelinePlaybookExplanation": {
        "provider": "ollama",
        "config": {
            "inference_url": "http://host.containers.internal:11434",
            "model_id": "mistral:instruct"}},
    "ModelPipelineRoleExplanation": {
        "provider": "ollama",
        "config": {
            "inference_url": "http://host.containers.internal:11434",
            "model_id": "mistral:instruct"}},
    "ModelPipelineChatBot": {
        "provider": "http",
        "config": {
            "inference_url": "http://localhost:8000",
            "model_id": "granite3-8b"}}
}"
```
