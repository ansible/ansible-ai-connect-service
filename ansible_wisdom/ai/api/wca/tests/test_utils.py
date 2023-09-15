from unittest import TestCase

from ai.api.wca.utils import is_org_id_invalid


class TestWCAApiKeyView(TestCase):
    def test_valid_org_id(self):
        self.assertFalse(is_org_id_invalid("123"))

    def test_invalid_org_id(self):
        self.assertTrue(is_org_id_invalid(None))
        self.assertTrue(is_org_id_invalid("abc"))
        self.assertTrue(is_org_id_invalid("-1"))
