"""
Test URLs
"""
from django.test import Client
from django.test.testcases import SimpleTestCase


class TestSchemaURLs(SimpleTestCase):
    def test_schema_endpoints(self):
        """
        Make sure schema/Swagger UI endpoints are not available in non-DEBUG environment.
        """
        c = Client()
        res = c.get('/api/schema/')
        self.assertEqual(res.status_code, 404)
        res = c.get('/api/schema/swagger-ui/')
        self.assertEqual(res.status_code, 404)
