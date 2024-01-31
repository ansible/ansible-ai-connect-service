import importlib
import os
from unittest.mock import patch

import django.conf
import main.settings.base
from django.test import SimpleTestCase
from oauth2_provider.settings import oauth2_settings


class TestSettings(SimpleTestCase):
    def test_oauth2(self):
        REFRESH_TOKEN_EXPIRE_SECONDS = oauth2_settings.REFRESH_TOKEN_EXPIRE_SECONDS
        self.assertGreater(REFRESH_TOKEN_EXPIRE_SECONDS, 0)
        self.assertLessEqual(REFRESH_TOKEN_EXPIRE_SECONDS, 864_000)

    @patch.dict(
        os.environ,
        {
            'SOCIAL_AUTH_GITHUB_TEAM_KEY': 'teamkey',
            'SOCIAL_AUTH_GITHUB_TEAM_SECRET': 'teamsecret',
            'SOCIAL_AUTH_GITHUB_TEAM_ID': '5678',
        },
    )
    def test_github_auth_team_with_id(self):
        module_name = os.getenv("DJANGO_SETTINGS_MODULE")
        settings_module = importlib.import_module(module_name)

        importlib.reload(main.settings.base)
        importlib.reload(settings_module)
        importlib.reload(django.conf)
        from django.conf import settings

        settings.configure(default_settings=settings_module)
        self.assertEqual(settings.USE_GITHUB_TEAM, True)
        self.assertEqual(settings.SOCIAL_AUTH_GITHUB_TEAM_KEY, 'teamkey')
        self.assertEqual(settings.SOCIAL_AUTH_GITHUB_TEAM_SECRET, 'teamsecret')
        self.assertEqual(settings.SOCIAL_AUTH_GITHUB_TEAM_ID, '5678')
        self.assertEqual(settings.SOCIAL_AUTH_GITHUB_TEAM_SCOPE, ["read:org"])
        self.assertEqual(settings.SOCIAL_AUTH_GITHUB_TEAM_EXTRA_DATA, ['login'])

    @patch.dict(
        os.environ,
        {
            'SOCIAL_AUTH_GITHUB_TEAM_KEY': 'teamkey',
            'SOCIAL_AUTH_GITHUB_TEAM_SECRET': 'teamsecret',
            'SOCIAL_AUTH_GITHUB_TEAM_ID': '',
        },
    )
    def test_github_auth_team_without_id(self):
        module_name = os.getenv("DJANGO_SETTINGS_MODULE")
        settings_module = importlib.import_module(module_name)

        importlib.reload(main.settings.base)
        importlib.reload(settings_module)
        importlib.reload(django.conf)
        from django.conf import settings

        settings.configure(default_settings=settings_module)
        self.assertEqual(settings.USE_GITHUB_TEAM, True)
        self.assertEqual(settings.SOCIAL_AUTH_GITHUB_TEAM_KEY, 'teamkey')
        self.assertEqual(settings.SOCIAL_AUTH_GITHUB_TEAM_SECRET, 'teamsecret')
        self.assertEqual(settings.SOCIAL_AUTH_GITHUB_TEAM_ID, 7188893)
        self.assertEqual(settings.SOCIAL_AUTH_GITHUB_TEAM_SCOPE, ["read:org"])
        self.assertEqual(settings.SOCIAL_AUTH_GITHUB_TEAM_EXTRA_DATA, ['login'])

    @patch.dict(
        os.environ,
        {
            'SOCIAL_AUTH_GITHUB_TEAM_KEY': '',
            'SOCIAL_AUTH_GITHUB_KEY': "key",
            'SOCIAL_AUTH_GITHUB_SECRET': 'secret',
        },
    )
    def test_github_auth_team_empty_key(self):
        module_name = os.getenv("DJANGO_SETTINGS_MODULE")
        settings_module = importlib.import_module(module_name)

        importlib.reload(main.settings.base)
        importlib.reload(settings_module)
        importlib.reload(django.conf)
        from django.conf import settings

        settings.configure(default_settings=settings_module)
        self.assertEqual(settings.USE_GITHUB_TEAM, False)
        self.assertEqual(settings.SOCIAL_AUTH_GITHUB_KEY, 'key')
        self.assertEqual(settings.SOCIAL_AUTH_GITHUB_SECRET, 'secret')
        self.assertEqual(settings.SOCIAL_AUTH_GITHUB_SCOPE, [""])
        self.assertEqual(settings.SOCIAL_AUTH_GITHUB_EXTRA_DATA, ['login'])
