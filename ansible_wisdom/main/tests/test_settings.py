from django.test import SimpleTestCase
from oauth2_provider.settings import oauth2_settings


class TestSettings(SimpleTestCase):
    def test_oauth2(self):
        REFRESH_TOKEN_EXPIRE_SECONDS = oauth2_settings.REFRESH_TOKEN_EXPIRE_SECONDS
        self.assertGreater(REFRESH_TOKEN_EXPIRE_SECONDS, 0)
        self.assertLessEqual(REFRESH_TOKEN_EXPIRE_SECONDS, 864_000)
