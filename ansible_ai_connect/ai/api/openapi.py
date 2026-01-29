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
