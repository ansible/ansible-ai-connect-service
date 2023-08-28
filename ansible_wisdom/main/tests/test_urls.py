from importlib import reload
from re import compile

import main.urls
from django.test import Client, TestCase, override_settings
from django.test.utils import setup_test_environment


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
