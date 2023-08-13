from importlib import reload
from re import compile

import main.urls
from django.test import TestCase, override_settings


class TestUrls(TestCase):
    @override_settings(DEBUG=True)
    def test_urlpatterns(self):
        reload(main.urls)
        r = compile("api/schema/")
        patterns = list(filter(lambda e: r.match(str(e.pattern)), main.urls.urlpatterns))
        self.assertEqual(len(patterns), 3)
