from django.test import TestCase

from ansible_ai_connect.main.settings.base import is_ssl_enabled


class TestBaseSettings(TestCase):

    def test_is_ssl_enabled_true(self):
        self.assertTrue(is_ssl_enabled("True"))
        self.assertTrue(is_ssl_enabled("TruE"))
        self.assertTrue(is_ssl_enabled("true"))
        self.assertTrue(is_ssl_enabled("t"))
        self.assertTrue(is_ssl_enabled("1"))

    def test_is_ssl_enabled_incorrect_value(self):
        self.assertTrue(is_ssl_enabled("Yes"))
        self.assertTrue(is_ssl_enabled("Ano"))
        self.assertTrue(is_ssl_enabled("No"))

    def test_is_ssl_enabled_false(self):
        self.assertFalse(is_ssl_enabled("False"))
        self.assertFalse(is_ssl_enabled("false"))
        self.assertFalse(is_ssl_enabled("f"))
        self.assertFalse(is_ssl_enabled("0"))
        self.assertFalse(is_ssl_enabled("-1"))
