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
import logging
import os
from copy import deepcopy
from typing import cast

from ansible_ai_connect.main.settings.types import t_model_mesh_api_type

logger = logging.getLogger(__name__)


def is_ssl_enabled(value: str) -> bool:
    """SSL should be enabled if value is not recognized"""
    disabled = value.lower() in ("false", "f", "0", "-1")
    return not disabled


def load_from_env_vars():
    # ==========================================
    # Model Provider
    # ------------------------------------------
    model_service_type: t_model_mesh_api_type = cast(
        t_model_mesh_api_type, os.getenv("ANSIBLE_AI_MODEL_MESH_API_TYPE") or "http"
    )
    model_service_url = (
        os.getenv("ANSIBLE_AI_MODEL_MESH_API_URL") or "https://model.wisdom.testing.ansible.com:443"
    )
    model_service_api_key = os.getenv("ANSIBLE_AI_MODEL_MESH_API_KEY")
    model_service_model_id = os.getenv("ANSIBLE_AI_MODEL_MESH_MODEL_ID")
    if "ANSIBLE_AI_MODEL_MESH_MODEL_NAME" in os.environ:
        logger.warning(
            "Use of ANSIBLE_AI_MODEL_MESH_MODEL_NAME is deprecated and "
            "should be replaced with ANSIBLE_AI_MODEL_MESH_MODEL_ID."
        )
        if "ANSIBLE_AI_MODEL_MESH_MODEL_ID" in os.environ:
            logger.warning(
                "Environment variable ANSIBLE_AI_MODEL_MESH_MODEL_ID is set "
                "and will take precedence."
            )
        else:
            logger.warning(
                "Setting the value of ANSIBLE_AI_MODEL_MESH_MODEL_ID to "
                "the value of ANSIBLE_AI_MODEL_MESH_MODEL_NAME."
            )
            model_service_model_id = os.getenv("ANSIBLE_AI_MODEL_MESH_MODEL_NAME")

    # Model API Timeout (in seconds). Default is None.
    model_service_timeout = (
        int(cast(int, os.getenv("ANSIBLE_AI_MODEL_MESH_API_TIMEOUT")))
        if os.getenv("ANSIBLE_AI_MODEL_MESH_API_TIMEOUT", "").isnumeric()
        else None
    )
    model_service_retry_count = int(os.getenv("ANSIBLE_WCA_RETRY_COUNT") or "4")
    model_service_verify_ssl = is_ssl_enabled(
        os.getenv("ANSIBLE_AI_MODEL_MESH_API_VERIFY_SSL", "True")
    )

    model_service_enable_health_check = (
        os.getenv("ENABLE_HEALTHCHECK_MODEL_MESH", "True").lower() == "true"
    )
    model_service_health_check_api_key = os.getenv("ANSIBLE_WCA_HEALTHCHECK_API_KEY")
    model_service_health_check_model_id = os.getenv("ANSIBLE_WCA_HEALTHCHECK_MODEL_ID")
    # ==========================================

    # ==========================================
    # Pipeline JSON configuration
    # ------------------------------------------
    if model_service_type == "wca":
        wca_saas_idp_url = os.getenv("ANSIBLE_WCA_IDP_URL") or "https://iam.cloud.ibm.com/identity"
        wca_saas_idp_login = os.getenv("ANSIBLE_WCA_IDP_LOGIN")
        wca_saas_idp_password = os.getenv("ANSIBLE_WCA_IDP_PASSWORD")
        wca_saas_one_click_default_api_key: str = (
            os.getenv("ANSIBLE_AI_ENABLE_ONE_CLICK_DEFAULT_API_KEY") or ""
        )
        wca_saas_one_click_default_model_id: str = (
            os.getenv("ANSIBLE_AI_ENABLE_ONE_CLICK_DEFAULT_MODEL_ID") or ""
        )
        model_pipeline_config = {
            "provider": "wca",
            "config": {
                "inference_url": model_service_url,
                "api_key": model_service_api_key,
                "model_id": model_service_model_id,
                "timeout": model_service_timeout,
                "verify_ssl": model_service_verify_ssl,
                "retry_count": model_service_retry_count,
                "health_check_api_key": model_service_health_check_api_key,
                "health_check_model_id": model_service_health_check_model_id,
                "idp_url": wca_saas_idp_url,
                "idp_login": wca_saas_idp_login,
                "idp_password": wca_saas_idp_password,
                "one_click_default_api_key": wca_saas_one_click_default_api_key,
                "one_click_default_model_id": wca_saas_one_click_default_model_id,
            },
        }
    elif model_service_type == "wca-onprem":
        wca_onprem_username = os.getenv("ANSIBLE_WCA_USERNAME")
        model_pipeline_config = {
            "provider": "wca-onprem",
            "config": {
                "inference_url": model_service_url,
                "api_key": model_service_api_key,
                "model_id": model_service_model_id,
                "timeout": model_service_timeout,
                "verify_ssl": model_service_verify_ssl,
                "retry_count": model_service_retry_count,
                "health_check_api_key": model_service_health_check_api_key,
                "health_check_model_id": model_service_health_check_model_id,
                "username": wca_onprem_username,
            },
        }
    elif model_service_type == "dummy":
        dummy_response_body = os.environ.get(
            "DUMMY_MODEL_RESPONSE_BODY",
            (
                '{"predictions":["ansible.builtin.apt:\\n  name: nginx\\n'
                '  update_cache: true\\n  state: present\\n"]}'
            ),
        )
        dummy_response_max_latency_msec = int(
            os.environ.get("DUMMY_MODEL_RESPONSE_MAX_LATENCY_MSEC", 3000)
        )
        dummy_response_latency_use_jitter = bool(
            os.environ.get("DUMMY_MODEL_RESPONSE_LATENCY_USE_JITTER", False)
        )
        model_pipeline_config = {
            "provider": "dummy",
            "config": {
                "inference_url": model_service_url,
                "body": dummy_response_body,
                "latency_max_msec": dummy_response_max_latency_msec,
                "latency_use_jitter": dummy_response_latency_use_jitter,
            },
        }
    elif model_service_type == "ollama":
        model_pipeline_config = {
            "provider": "ollama",
            "config": {
                "inference_url": model_service_url,
                "model_id": model_service_model_id,
                "timeout": model_service_timeout,
            },
        }
    else:
        model_pipeline_config = {
            "provider": "wca-dummy",
            "config": {
                "inference_url": model_service_url,
            },
        }

    # Lazy import to avoid circular dependencies
    from ansible_ai_connect.ai.api.model_pipelines.pipelines import MetaData  # noqa
    from ansible_ai_connect.ai.api.model_pipelines.registry import (  # noqa
        REGISTRY_ENTRY,
    )

    pipelines = [i for i in REGISTRY_ENTRY.keys() if issubclass(i, MetaData)]
    model_pipelines_config: dict = {k.__name__: deepcopy(model_pipeline_config) for k in pipelines}

    # The ChatBot does not use the same configuration as everything else
    chatbot_service_url = os.getenv("CHATBOT_URL")
    chatbot_service_model_id = os.getenv("CHATBOT_DEFAULT_MODEL")
    chatbot_service_enable_health_check = (
        os.getenv("ENABLE_HEALTHCHECK_CHATBOT_SERVICE", "True").lower() == "true"
    )
    model_pipelines_config["ModelPipelineChatBot"] = {
        "provider": "http",
        "config": {
            "inference_url": chatbot_service_url or "http://localhost:8000",
            "model_id": chatbot_service_model_id or "granite3-8b",
            "verify_ssl": model_service_verify_ssl,
            "stream": False,
        },
    }
    model_pipelines_config["ModelPipelineStreamingChatBot"] = {
        "provider": "http",
        "config": {
            "inference_url": chatbot_service_url or "http://localhost:8000",
            "model_id": chatbot_service_model_id or "granite3-8b",
            "verify_ssl": model_service_verify_ssl,
            "stream": True,
        },
    }

    # Enable Health Checks where we have them implemented
    model_pipelines_config["ModelPipelineCompletions"]["config"][
        "enable_health_check"
    ] = model_service_enable_health_check
    model_pipelines_config["ModelPipelineChatBot"]["config"][
        "enable_health_check"
    ] = chatbot_service_enable_health_check
    # ==========================================

    return json.dumps(model_pipelines_config)
