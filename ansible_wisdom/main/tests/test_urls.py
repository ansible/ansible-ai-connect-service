from importlib import reload
from re import compile

import main.urls
from django.test import Client, TestCase, override_settings


class TestUrls(TestCase):
    @override_settings(DEBUG=True)
    def test_urlpatterns(self):
        reload(main.urls)
        routes = [
            'api/schema/',
            'api/schema/swagger-ui/',
            'api/schema/redoc/',
        ]
        r = compile("api/schema/")
        patterns = list(
            filter(r.match, [str(pattern.pattern) for pattern in main.urls.urlpatterns])
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

    def test_telemetry_patterns_when_enabled(self):
        reload(main.urls)
        r = compile("api/v0/telemetry/")
        patterns = list(
            filter(r.match, [str(pattern.pattern) for pattern in main.urls.urlpatterns])
        )
        self.assertEqual(1, len(patterns))

    @override_settings(ADMIN_PORTAL_TELEMETRY_OPT_ENABLED=False)
    def test_telemetry_patterns_when_disabled(self):
        reload(main.urls)
        r = compile("api/v0/telemetry/")
        patterns = list(
            filter(r.match, [str(pattern.pattern) for pattern in main.urls.urlpatterns])
        )
        self.assertEqual(0, len(patterns))
