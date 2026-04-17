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

from ansible_ai_connect.ai.api.openapi import (
    postprocessing_fix_additional_properties,
    preprocessing_filter_spec,
)
from ansible_ai_connect.test_utils import WisdomTestCase


class TestOpenAPI(WisdomTestCase):

    def test_openapi_filter(self):
        endpoints = [
            ("/api/v1/service-index/resources/", None, None, None),
            ("/api/v1/me/", None, None, None),
            ("/api/v1/service-index/metadata/", None, None, None),
        ]
        filtered_endpoints = preprocessing_filter_spec(endpoints)
        self.assertEqual(len(filtered_endpoints), 1)
        self.assertEqual(filtered_endpoints[0][0], "/api/v1/me/")

    def test_postprocessing_fix_empty_additional_properties(self):
        """Test that empty additionalProperties {} is replaced with true."""
        spec = {
            "components": {
                "schemas": {
                    "TestSchema": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                        },
                        "additionalProperties": {},  # Empty object - should be fixed
                    }
                }
            }
        }

        result = postprocessing_fix_additional_properties(spec, None, None, None)

        self.assertEqual(
            result["components"]["schemas"]["TestSchema"]["additionalProperties"],
            True,
        )

    def test_postprocessing_preserves_valid_additional_properties(self):
        """Test that valid additionalProperties values are preserved."""
        spec = {
            "components": {
                "schemas": {
                    "SchemaWithTrue": {
                        "type": "object",
                        "additionalProperties": True,  # Already correct
                    },
                    "SchemaWithFalse": {
                        "type": "object",
                        "additionalProperties": False,  # Explicit false
                    },
                    "SchemaWithSchema": {
                        "type": "object",
                        "additionalProperties": {"type": "string"},  # Schema definition
                    },
                }
            }
        }

        result = postprocessing_fix_additional_properties(spec, None, None, None)

        # These should remain unchanged
        self.assertEqual(
            result["components"]["schemas"]["SchemaWithTrue"]["additionalProperties"],
            True,
        )
        self.assertEqual(
            result["components"]["schemas"]["SchemaWithFalse"]["additionalProperties"],
            False,
        )
        self.assertEqual(
            result["components"]["schemas"]["SchemaWithSchema"]["additionalProperties"],
            {"type": "string"},
        )

    def test_postprocessing_fixes_nested_schemas(self):
        """Test that nested schemas with empty additionalProperties are fixed."""
        spec = {
            "components": {
                "schemas": {
                    "ParentSchema": {
                        "type": "object",
                        "properties": {
                            "child": {
                                "type": "object",
                                "additionalProperties": {},  # Nested empty object
                            }
                        },
                    }
                }
            }
        }

        result = postprocessing_fix_additional_properties(spec, None, None, None)

        self.assertEqual(
            result["components"]["schemas"]["ParentSchema"]["properties"]["child"][
                "additionalProperties"
            ],
            True,
        )

    def test_postprocessing_fixes_inline_path_schemas(self):
        """Test that inline schemas in paths are fixed."""
        spec = {
            "paths": {
                "/test": {
                    "get": {
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "additionalProperties": {},
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        result = postprocessing_fix_additional_properties(spec, None, None, None)

        self.assertEqual(
            result["paths"]["/test"]["get"]["responses"]["200"]["content"]["application/json"][
                "schema"
            ]["additionalProperties"],
            True,
        )

    def test_postprocessing_handles_arrays_with_schemas(self):
        """Test that schemas in arrays are processed."""
        spec = {
            "components": {
                "schemas": {
                    "ArraySchema": {
                        "type": "array",
                        "items": [
                            {
                                "type": "object",
                                "additionalProperties": {},  # In array
                            }
                        ],
                    }
                }
            }
        }

        result = postprocessing_fix_additional_properties(spec, None, None, None)

        self.assertEqual(
            result["components"]["schemas"]["ArraySchema"]["items"][0]["additionalProperties"],
            True,
        )

    def test_postprocessing_handles_missing_components(self):
        """Test that specs without components are handled gracefully."""
        spec = {"paths": {}}

        # Should not raise an error
        result = postprocessing_fix_additional_properties(spec, None, None, None)

        self.assertEqual(result, spec)
