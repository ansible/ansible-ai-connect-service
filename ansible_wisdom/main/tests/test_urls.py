from importlib import reload
from re import compile

import main.urls
from django.test import TestCase, override_settings


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
