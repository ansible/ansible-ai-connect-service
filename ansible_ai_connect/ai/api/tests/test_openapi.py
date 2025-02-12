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

from ansible_ai_connect.ai.api.openapi import preprocessing_filter_spec
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
