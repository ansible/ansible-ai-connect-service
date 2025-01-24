# Model Pipelines

Ansible AI Connect is becoming feature rich.

It supports API for the following features:
- Code completions
- Content match
- Playbook Generation
- Role Generation
- Playbook Explanation
- Chat Bot

"Model Pipelines" provides a mechanism to support different _pipelines_ and configuration for each of these features for different providers. Different providers require different configuration information.

## Pipelines

A pipeline can exist for each feature for each type of provider.

Types of provider are:
- `grpc`
- `http`
- `dummy`
- `wca`
- `wca-onprem`
- `wca-dummy`
- `ollama`
- `llamacpp`
- `nop`

### Implementing pipelines

Implementations of a pipeline, for a particular provider, for a particular feature should extend the applicable base class; implementing the `invoke(..)` method accordingly:
- `ModelPipelineCompletions`
- `ModelPipelineContentMatch`
- `ModelPipelinePlaybookGeneration`
- `ModelPipelineRoleGeneration`
- `ModelPipelinePlaybookExplanation`
- `ModelPipelineChatBot`

### Registering pipelines

Implementations of pipelines, per provider, per feature are dynamically registered. To register a pipeline the implementing class should be decorated with `@Register(api_type="<type>")`.

In addition to the supported features themselves implementations for the following must also be provided and registered:
- `MetaData`

  A class providing basic meta-data for all features for the applicable provider.

  For example API Key, Model ID, Timeout etc.


- `PipelineConfiguration`

  A class representing the pipelines configuration parameters.


- `Serializer`

  A class that can deserialise configuration JSON/YAML into the target `PipelineConfiguration` class.

### Default implementations

A "No Operation" pipeline is registered by default for each provider and each feature where a concrete implementation is not explicitly available.

### Lookup

A registry is constructed at start-up, containing information of configured pipelines for all providers for all features.
```
REGISTRY = {
    "http": {
        MetaData: <Implementing class>,
        ModelPipelineCompletions: <Implementing class>
        ModelPipelineContentMatch: <Implementing class>
        ModelPipelinePlaybookGeneration: <Implementing class>
        ModelPipelineRoleGeneration: <Implementing class>
        ModelPipelinePlaybookExplanation: <Implementing class>
        ModelPipelineChatBot: <Implementing class>
        PipelineConfiguration: <Implementing class>
        Serializer: <Implementing class>
    }
    ...
}
```

To invoke a pipeline for a particular feature the instance for the configured provider can be retrieved from the `ai` Django application:
```
pipeline: ModelPipelinePlaybookGeneration =
    apps
    .get_app_config("ai")
    .get_model_pipeline(ModelPipelinePlaybookGeneration)
```
The pipeline can then be invoked:
```
playbook, outline, warnings = pipeline.invoke(
    PlaybookGenerationParameters.init(
        request=request,
        text=self.validated_data["text"],
        custom_prompt=self.validated_data["customPrompt"],
        create_outline=self.validated_data["createOutline"],
        outline=self.validated_data["outline"],
        generation_id=self.validated_data["generationId"],
        model_id=self.req_model_id,
    )
)
```
The code is identical irrespective of which provider is configured.

### Configuration

Refer to the [examples](../../../../docs/config).
