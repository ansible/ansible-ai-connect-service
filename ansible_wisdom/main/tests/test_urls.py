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

from django.test import Client, TestCase, override_settings

import ansible_ai_connect.main.urls


class TestUrls(TestCase):
    @override_settings(DEBUG=True)
    def test_urlpatterns(self):
        reload(ansible_ai_connect.main.urls)
        routes = [
            'api/schema/',
            'api/schema/swagger-ui/',
            'api/schema/redoc/',
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
        self.assertIn(
            "style-src 'self' 'unsafe-inline'", response.headers.get('Content-Security-Policy')
        )
        self.assertIn("default-src 'self' data:", response.headers.get('Content-Security-Policy'))

    def test_telemetry_patterns(self):
        reload(ansible_ai_connect.main.urls)
        r = compile("api/v0/telemetry/")
        patterns = list(
            filter(
                r.match,
                [str(pattern.pattern) for pattern in ansible_ai_connect.main.urls.urlpatterns],
            )
        )
        self.assertEqual(1, len(patterns))

    @override_settings(DEPLOYMENT_MODE="saas")
    def test_metrics_url_saas(self):
        self._do_test_metrics_url()

    @override_settings(DEPLOYMENT_MODE="upstream")
    def test_metrics_url_upstream(self):
        self._do_test_metrics_url()

    @override_settings(DEPLOYMENT_MODE="onprem")
    def test_metrics_url_onprem(self):
        self._do_test_metrics_url(False)

    def _do_test_metrics_url(self, include_metrics_url: bool = True):
        included_url_patterns = []
        reload(ansible_ai_connect.main.urls)
        for pattern in ansible_ai_connect.main.urls.urlpatterns:
            included_url_patterns += (
                [str(p.pattern) for p in pattern.url_patterns]
                if hasattr(pattern, "url_patterns")
                else []
            )

        if include_metrics_url:
            self.assertIn("metrics", included_url_patterns)
        else:
            self.assertNotIn("metrics", included_url_patterns)
