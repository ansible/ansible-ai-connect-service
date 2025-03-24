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
from json import JSONDecodeError

import yaml
from django.test import override_settings
from yaml import YAMLError

from ansible_ai_connect.ai.api.model_pipelines.config_loader import load_config
from ansible_ai_connect.ai.api.model_pipelines.config_providers import Configuration
from ansible_ai_connect.ai.api.model_pipelines.pipelines import MetaData
from ansible_ai_connect.ai.api.model_pipelines.registry import REGISTRY_ENTRY
from ansible_ai_connect.ai.api.model_pipelines.tests import mock_config
from ansible_ai_connect.test_utils import WisdomTestCase

EMPTY = {
    "MetaData": {
        "provider": "dummy",
    },
}


def _convert_json_to_yaml(json_config: str):
    yaml_config = yaml.safe_load(json_config)
    return yaml.safe_dump(yaml_config)


class TestConfigLoader(WisdomTestCase):

    def assert_config(self):
        config: Configuration = load_config()
        pipelines = [i for i in REGISTRY_ENTRY.keys() if issubclass(i, MetaData)]
        for k in pipelines:
            self.assertTrue(k.__name__ in config)

    def assert_invalid_config(self):
        with self.assertRaises(ExceptionGroup) as e:
            load_config()
        exceptions = e.exception.exceptions
        self.assertEqual(len(exceptions), 2)
        self.assertIsInstance(exceptions[0], JSONDecodeError)
        self.assertIsInstance(exceptions[1], YAMLError)

    @override_settings(ANSIBLE_AI_MODEL_MESH_CONFIG=None)
    def test_config_undefined(self):
        self.assert_config()

    @override_settings(ANSIBLE_AI_MODEL_MESH_CONFIG=json.dumps(EMPTY))
    def test_config_empty(self):
        self.assert_config()

    @override_settings(ANSIBLE_AI_MODEL_MESH_CONFIG="")
    def test_config_empty_string(self):
        self.assert_config()

    @override_settings(ANSIBLE_AI_MODEL_MESH_CONFIG='{"MetaData" : {')
    def test_config_invalid_json(self):
        self.assert_invalid_config()

    @override_settings(ANSIBLE_AI_MODEL_MESH_CONFIG="MetaData:\nbanana")
    def test_config_invalid_yaml(self):
        self.assert_invalid_config()

    @override_settings(ANSIBLE_AI_MODEL_MESH_CONFIG=mock_config("ollama"))
    def test_config_json(self):
        self.assert_config()

    @override_settings(ANSIBLE_AI_MODEL_MESH_CONFIG=_convert_json_to_yaml(mock_config("ollama")))
    def test_config_yaml(self):
        self.assert_config()
