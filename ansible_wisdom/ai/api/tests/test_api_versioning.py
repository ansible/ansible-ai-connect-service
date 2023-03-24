from django.shortcuts import reverse
from django.test import TestCase
from rest_framework.test import APIClient

WISDOM_API_VERSION = "v0"


class TestAPIVersioning(TestCase):
    def setUp(self) -> None:
        self.api_url = reverse(f'{WISDOM_API_VERSION}:completions')
        self.client = APIClient()

    def test_ansible_wisdom_completion_url(self):
        print("** TEST versioning: test_ansible_wisdom_completion_url ** ", self.api_url)

    def test_completion_request(self):
        response = self.client.get(self.api_url)
        print("** TEST versioning: test_completion_request ** ", response.content)

    def test_api_v0_test_endpoint(self):
        # Make a GET request to the v1 test endpoint
        response = self.client.get(f'/api/{WISDOM_API_VERSION}/ai/completions/')

        # Assert that the response status code is 200 OK
        self.assertEqual(response.status_code, 200)

        # Assert that the response contains the expected data
        expected_data = {'message': 'This is a test'}
        self.assertEqual(response.json(), expected_data)
