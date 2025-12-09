#  Copyright Red Hat
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
import json
from typing import TypeVar

from ansible_ai_connect.ai.api.model_pipelines.dummy.configuration import (
    DummyConfiguration,
)
from ansible_ai_connect.ai.api.model_pipelines.http.configuration import (
    HttpConfiguration,
)
from ansible_ai_connect.ai.api.model_pipelines.llamacpp.configuration import (
    LlamaCppConfiguration,
)
from ansible_ai_connect.ai.api.model_pipelines.llamastack.configuration import (
    LlamaStackConfiguration,
)
from ansible_ai_connect.ai.api.model_pipelines.nop.configuration import NopConfiguration
from ansible_ai_connect.ai.api.model_pipelines.ollama.configuration import (
    OllamaConfiguration,
)
from ansible_ai_connect.ai.api.model_pipelines.registry import REGISTRY, REGISTRY_ENTRY
from ansible_ai_connect.ai.api.model_pipelines.wca.configuration_dummy import (
    WCADummyConfiguration,
)
from ansible_ai_connect.ai.api.model_pipelines.wca.configuration_onprem import (
    WCAOnPremConfiguration,
)
from ansible_ai_connect.ai.api.model_pipelines.wca.configuration_saas import (
    WCASaaSConfiguration,
)
from ansible_ai_connect.main.settings.types import t_model_mesh_api_type

T = TypeVar("T")


def mock_config(pipeline_provider: t_model_mesh_api_type, **kwargs):
    config = {}
    pipeline_config = mock_pipeline_config(pipeline_provider, **kwargs).__dict__
    for pipeline in REGISTRY_ENTRY:
        if REGISTRY[pipeline_provider][pipeline]:
            config = {
                **config,
                pipeline.__name__: {"provider": pipeline_provider, "config": pipeline_config},
            }
    return json.dumps(config)


def extract(name: str, default: T, **kwargs) -> T:
    result: T = default
    if name in kwargs:
        result = kwargs[name]
    return result


def mock_pipeline_config(pipeline_provider: t_model_mesh_api_type, **kwargs):
    match pipeline_provider:
        case "dummy":
            return DummyConfiguration(
                enable_health_check=extract("enable_health_check", False, **kwargs),
                latency_use_jitter=extract("latency_use_jitter", False, **kwargs),
                latency_max_msec=extract("latency_max_msec", 0, **kwargs),
                body=extract("body", "body", **kwargs),
            )
        case "http":
            return HttpConfiguration(
                inference_url=extract("inference_url", "http://localhost", **kwargs),
                model_id=extract("model_id", "a-model-id", **kwargs),
                timeout=extract("timeout", 1000, **kwargs),
                enable_health_check=extract("enable_health_check", False, **kwargs),
                verify_ssl=extract("verify_ssl", False, **kwargs),
                stream=extract("stream", False, **kwargs),
                mcp_servers=extract("mcp_servers", [], **kwargs),
                ca_cert_file=extract("ca_cert_file", None, **kwargs),
            )
        case "llamacpp":
            return LlamaCppConfiguration(
                inference_url=extract("inference_url", "http://localhost", **kwargs),
                model_id=extract("model_id", "a-model-id", **kwargs),
                timeout=extract("timeout", 1000, **kwargs),
                enable_health_check=extract("enable_health_check", False, **kwargs),
                verify_ssl=extract("verify_ssl", False, **kwargs),
            )
        case "llama-stack":
            return LlamaStackConfiguration(
                inference_url=extract("inference_url", "http://localhost", **kwargs),
                model_id=extract("model_id", "a-model-id", **kwargs),
                timeout=extract("timeout", 1000, **kwargs),
                enable_health_check=extract("enable_health_check", False, **kwargs),
            )
        case "nop":
            return NopConfiguration()
        case "ollama":
            return OllamaConfiguration(
                inference_url=extract("inference_url", "http://localhost", **kwargs),
                model_id=extract("model_id", "a-model-id", **kwargs),
                timeout=extract("timeout", 1000, **kwargs),
                enable_health_check=extract("enable_health_check", False, **kwargs),
            )
        case "wca":
            return WCASaaSConfiguration(
                inference_url=extract("inference_url", "http://localhost", **kwargs),
                api_key=extract("api_key", "an-api-key", **kwargs),
                model_id=extract("model_id", "a-model-id", **kwargs),
                timeout=extract("timeout", 1000, **kwargs),
                enable_health_check=extract("enable_health_check", False, **kwargs),
                verify_ssl=extract("verify_ssl", False, **kwargs),
                retry_count=extract("retry_count", 4, **kwargs),
                health_check_api_key=extract(
                    "health_check_api_key", "a-healthcheck-api-key", **kwargs
                ),
                health_check_model_id=extract(
                    "health_check_model_id", "a-healthcheck-model-id", **kwargs
                ),
                idp_url=extract("idp_url", "an-idp-url", **kwargs),
                idp_login=extract("idp_login", "an-idp-login", **kwargs),
                idp_password=extract("idp_password", "an-idp-password", **kwargs),
                one_click_default_api_key=extract(
                    "one_click_default_api_key", "one-click-default-api-key", **kwargs
                ),
                one_click_default_model_id=extract(
                    "one_click_default_model_id", "one-click-default-model-id", **kwargs
                ),
                enable_anonymization=extract("enable_anonymization", True, **kwargs),
            )
        case "wca-onprem":
            return WCAOnPremConfiguration(
                inference_url=extract("inference_url", "http://localhost", **kwargs),
                api_key=extract("api_key", "an-api-key", **kwargs),
                model_id=extract("model_id", "a-model-id", **kwargs),
                timeout=extract("timeout", 1000, **kwargs),
                enable_health_check=extract("enable_health_check", False, **kwargs),
                verify_ssl=extract("verify_ssl", False, **kwargs),
                retry_count=extract("retry_count", 4, **kwargs),
                health_check_api_key=extract(
                    "health_check_api_key", "a-healthcheck-api-key", **kwargs
                ),
                health_check_model_id=extract(
                    "health_check_model_id", "a-healthcheck-model-id", **kwargs
                ),
                username=extract("username", "a-username", **kwargs),
                enable_anonymization=extract("enable_anonymization", True, **kwargs),
            )
        case "wca-dummy":
            return WCADummyConfiguration(
                inference_url=extract("inference_url", "http://localhost", **kwargs)
            )
    return {}
