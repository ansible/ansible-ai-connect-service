from django.test import override_settings
from rest_framework.test import APITransactionTestCase

from ansible_ai_connect.ai.resource_api import get_service_type


class TestResourceAPI(APITransactionTestCase):

    def test_service_type_when_resource_service_not_defined(self):
        self.assertEqual(get_service_type(), "aap")

    @override_settings(RESOURCE_SERVER__URL=None)
    def test_service_type_when_resource_service_url_is_empty(self):
        self.assertEqual(get_service_type(), "aap")

    @override_settings(RESOURCE_SERVER=None)
    def test_service_type_when_resource_service_is_empty(self):
        self.assertEqual(get_service_type(), "aap")

    @override_settings(RESOURCE_SERVER__URL="https://localhost")
    def test_service_type_when_resource_service_url_has_value(self):
        self.assertEqual(get_service_type(), "lightspeed")

    @override_settings(RESOURCE_SERVER=dict(URL="https://localhost"))
    def test_service_type_when_resource_service_has_value(self):
        self.assertEqual(get_service_type(), "lightspeed")
