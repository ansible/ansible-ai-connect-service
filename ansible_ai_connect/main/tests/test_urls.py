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

from importlib import reload
from re import compile

from django.conf import settings
from django.test import Client, TestCase, override_settings
from django.urls import resolve

import ansible_ai_connect.main.urls


class TestUrls(TestCase):
    @override_settings(DEBUG=True)
    def test_urlpatterns(self):
        reload(ansible_ai_connect.main.urls)
        routes = [
            "api/schema/",
            "api/schema/swagger-ui/",
            "api/schema/redoc/",
        ]
        r = compile("api/schema/")
        patterns = list(
            filter(
                r.match,
                [str(pattern.pattern) for pattern in ansible_ai_connect.main.urls.urlpatterns],
            )
        )
        self.assertCountEqual(routes, patterns)

    @override_settings(CSP_REPORT_ONLY=False)
    def test_headers(self):
        client = Client()
        response = client.get("/")
        csp_headers = response.headers.get("Content-Security-Policy")
        self.assertNotIn("style-src 'self' 'unsafe-inline'", csp_headers)
        self.assertIn("default-src 'self' data:", csp_headers)
        self.assertIn("connect-src 'self'", csp_headers)

    def test_telemetry_patterns(self):
        api_versions = settings.REST_FRAMEWORK["ALLOWED_VERSIONS"]
        self.assertGreater(len(api_versions), 0)
        for api_version in api_versions:
            match = resolve(f"/api/{api_version}/telemetry/")
            self.assertEqual(match.url_name, "telemetry_settings")
            self.assertEqual(match.view_name, f"{api_version}:telemetry_settings")
