from unittest import TestCase

from ai.api.wca.utils import is_org_id_valid


class TestWCAApiKeyView(TestCase):
    def test_valid_org_id(self):
        self.assertTrue(is_org_id_valid("123"))

    def test_invalid_org_id(self):
        self.assertFalse(is_org_id_valid(None))
        self.assertFalse(is_org_id_valid("abc"))
        self.assertFalse(is_org_id_valid("-1"))
