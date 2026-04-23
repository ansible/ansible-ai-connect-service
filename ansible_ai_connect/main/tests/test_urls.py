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
        self.assertIn("base-uri 'self'", csp_headers)
        self.assertIn("form-action 'self'", csp_headers)
        self.assertIn("vscode:", csp_headers)
        # Check loopback patterns with port wildcards for dynamic OAuth ports
        self.assertIn("http://127.0.0.1:*", csp_headers)
        self.assertIn("http://[::1]:*", csp_headers)
        self.assertIn("http://localhost:*", csp_headers)
        # Ensure no wildcard schemes that would allow any http/https URL
        # Check for both space and semicolon separators
        self.assertNotIn("http: ", csp_headers)
        self.assertNotIn("http:;", csp_headers)
        self.assertNotIn("https: ", csp_headers)
        self.assertNotIn("https:;", csp_headers)
        self.assertIn("frame-ancestors 'none'", csp_headers)

    def test_csp_oauth_origin_parsing(self):
        """Test URL parsing logic for OAuth origins in CSP configuration"""
        from ansible_ai_connect.main.settings.base import _extract_oauth_origins

        # Test single URL
        result = _extract_oauth_origins("https://aap.example.com:8443/api/v2")
        self.assertEqual(result, ("https://aap.example.com:8443",))

        # Test multiple URLs
        result = _extract_oauth_origins(
            "https://aap.example.com:8443",
            "https://sso.redhat.com/auth/realms/test",
        )
        self.assertEqual(
            result,
            ("https://aap.example.com:8443", "https://sso.redhat.com"),
        )

        # Test with None values (should be skipped)
        result = _extract_oauth_origins(None, "https://sso.redhat.com")
        self.assertEqual(result, ("https://sso.redhat.com",))

        # Test with all None values
        result = _extract_oauth_origins(None, None)
        self.assertEqual(result, ())

        # Test with empty string (should be skipped)
        result = _extract_oauth_origins("", "https://sso.redhat.com")
        self.assertEqual(result, ("https://sso.redhat.com",))

        # Test with localhost and port
        result = _extract_oauth_origins("http://localhost:8080/api")
        self.assertEqual(result, ("http://localhost:8080",))

        # Test that ports are preserved (netloc, not hostname)
        result = _extract_oauth_origins("https://aap.example.com:9080")
        self.assertEqual(result, ("https://aap.example.com:9080",))

        # Test standard ports (no explicit port in URL)
        result = _extract_oauth_origins("https://sso.redhat.com/path")
        self.assertEqual(result, ("https://sso.redhat.com",))

        # Test invalid URL (no scheme)
        result = _extract_oauth_origins("example.com")
        self.assertEqual(result, ())

        # Test URL with only scheme (no netloc)
        result = _extract_oauth_origins("http://")
        self.assertEqual(result, ())

    def test_telemetry_patterns(self):
        api_versions = settings.REST_FRAMEWORK["ALLOWED_VERSIONS"]
        self.assertGreater(len(api_versions), 0)
        for api_version in api_versions:
            match = resolve(f"/api/{api_version}/telemetry/")
            self.assertEqual(match.url_name, "telemetry_settings")
            self.assertEqual(match.view_name, f"{api_version}:telemetry_settings")
