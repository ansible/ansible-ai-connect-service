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

INTERNAL_PATHS = ["/api/v1/service-index", "/check"]


def preprocessing_filter_spec(endpoints):
    filtered = []

    for path, path_regex, method, callback in endpoints:
        if any(path.startswith(internal_path) for internal_path in INTERNAL_PATHS):
            # do not add internal endpoints to schema
            continue
        filtered.append((path, path_regex, method, callback))
    return filtered


def postprocessing_fix_additional_properties(result, generator, request, public):
    """
    Fix empty additionalProperties objects that cause ZAP parser failures.

    drf-spectacular generates 'additionalProperties: {}' for DictField without
    a child parameter. This empty object is ambiguous and causes some OpenAPI
    parsers (including ZAP) to fail with NullPointerException.

    This hook replaces 'additionalProperties: {}' with 'additionalProperties: true'
    which correctly represents "allow any additional properties".
    """

    def fix_schema(schema):
        """Recursively fix additionalProperties in schema objects."""
        if not isinstance(schema, dict):
            return schema

        # Fix additionalProperties: {} → additionalProperties: true
        if "additionalProperties" in schema:
            if schema["additionalProperties"] == {}:
                schema["additionalProperties"] = True

        # Recursively process nested objects
        for key, value in schema.items():
            if isinstance(value, dict):
                fix_schema(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        fix_schema(item)

        return schema

    # Fix in components/schemas
    if "components" in result and "schemas" in result["components"]:
        for schema_name, schema_def in result["components"]["schemas"].items():
            fix_schema(schema_def)

    # Fix in paths (inline schemas)
    if "paths" in result:
        for path_def in result["paths"].values():
            fix_schema(path_def)

    return result
