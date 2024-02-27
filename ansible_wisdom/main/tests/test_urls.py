from importlib import reload
from re import compile

from django.test import Client, TestCase, override_settings

import ansible_wisdom.main.urls


class TestUrls(TestCase):
    @override_settings(DEBUG=True)
    def test_urlpatterns(self):
        reload(ansible_wisdom.main.urls)
        routes = [
            'api/schema/',
            'api/schema/swagger-ui/',
            'api/schema/redoc/',
        ]
        r = compile("api/schema/")
        patterns = list(
            filter(
                r.match, [str(pattern.pattern) for pattern in ansible_wisdom.main.urls.urlpatterns]
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
        r = compile("api/v0/telemetry/")
        patterns = list(
            filter(
                r.match, [str(pattern.pattern) for pattern in ansible_wisdom.main.urls.urlpatterns]
            )
        )
        self.assertEqual(1, len(patterns))
