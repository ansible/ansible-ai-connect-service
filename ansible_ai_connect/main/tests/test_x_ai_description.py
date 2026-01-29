#!/usr/bin/env python3
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
import os

import yaml
from django.test import TestCase

_current_dir_path = os.path.dirname(__file__)

X_AI_DESCRIPTION = "x-ai-description"
X_AI_DESCRIPTION_MIN_LENGTH = 0
X_AI_DESCRIPTION_MAX_LENGTH = 300


class XAIDescription(TestCase):
    openapi_schema_path = os.path.join(
        _current_dir_path, "..", "..", "..", "tools", "openapi-schema"
    )

    def setUp(self):
        self.openapi_schema_path_yaml = os.path.join(
            self.openapi_schema_path, "ansible-ai-connect-service.yaml"
        )
        self.openapi_schema_path_json = os.path.join(
            self.openapi_schema_path, "ansible-ai-connect-service.json"
        )

    def assert_schema_x_ai_description(self, schema):
        schema_paths = schema.get("paths", None)
        self.assertIsNotNone(schema_paths)
        self.assertTrue(len(schema_paths) > 0)

        operations_count = 0
        for path, operations in schema_paths.items():
            for method, operation in operations.items():
                if isinstance(operation, dict):
                    self.assertIn(X_AI_DESCRIPTION, operation)
                    x_ai_description = operation.get(X_AI_DESCRIPTION)
                    self.assertIsInstance(x_ai_description, str)
                    self.assertTrue(
                        X_AI_DESCRIPTION_MIN_LENGTH
                        < len(x_ai_description)
                        < X_AI_DESCRIPTION_MAX_LENGTH,
                        f"wrong string length ({len(x_ai_description)}) for: '{x_ai_description}', "
                        f"minimum allowed: {X_AI_DESCRIPTION_MIN_LENGTH}, "
                        f"maximum allowed: {X_AI_DESCRIPTION_MAX_LENGTH} ",
                    )
                    operations_count += 1

        assert operations_count > 0

    def test_openapi_schema_yaml(self):
        self.assertTrue(os.path.exists(self.openapi_schema_path_yaml))
        with open(os.path.join(self.openapi_schema_path_yaml)) as f:
            schema = yaml.safe_load(f)
        self.assert_schema_x_ai_description(schema)

    def test_openapi_schema_json(self):
        self.assertTrue(os.path.exists(self.openapi_schema_path_json))
        with open(os.path.join(self.openapi_schema_path_json)) as f:
            schema = json.load(f)
        self.assert_schema_x_ai_description(schema)
