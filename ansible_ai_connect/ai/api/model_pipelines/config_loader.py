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
from json import JSONDecodeError

import yaml
from django.conf import settings
from yaml import YAMLError

from ansible_ai_connect.ai.api.model_pipelines.config_providers import Configuration
from ansible_ai_connect.ai.api.model_pipelines.config_serializers import (
    ConfigurationSerializer,
)

logger = logging.getLogger(__name__)


def load_config() -> Configuration:
    # yaml.safe_load(..) seems to also support loading JSON. Nice.
    # However, try to load JSON with the correct _loader_ first in case of corner cases
    errors: [Exception] = []
    result = load_json()
    if isinstance(result, Exception):
        errors.append(result)
        result = load_yaml()
        if isinstance(result, Exception):
            errors.append(result)
        else:
            errors = []

    if len(errors) > 0:
        raise ExceptionGroup("Unable to parse ANSIBLE_AI_MODEL_MESH_CONFIG", errors)

    serializer = ConfigurationSerializer(data=result)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return serializer.instance


def load_json() -> str | Exception:
    try:
        logger.info("Attempting to parse ANSIBLE_AI_MODEL_MESH_CONFIG as JSON...")
        return json.loads(settings.ANSIBLE_AI_MODEL_MESH_CONFIG)
    except JSONDecodeError as e:
        logger.exception(f"An error occurring parsing ANSIBLE_AI_MODEL_MESH_CONFIG as JSON:\n{e}")
        return e


def load_yaml() -> str | Exception:
    try:
        logger.info("Attempting to parse ANSIBLE_AI_MODEL_MESH_CONFIG as YAML...")
        y = yaml.safe_load(settings.ANSIBLE_AI_MODEL_MESH_CONFIG)
        return y
    except YAMLError as e:
        logger.exception(f"An error occurring parsing ANSIBLE_AI_MODEL_MESH_CONFIG as YAML:\n{e}")
        return e
