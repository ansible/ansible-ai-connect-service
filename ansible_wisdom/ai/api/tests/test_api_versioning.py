from http import HTTPStatus
from unittest.mock import patch
from django.shortcuts import reverse
from .test_views import WisdomServiceAPITestCaseBase

WISDOM_API_VERSION = "v0"


class TestAPIVersioning(WisdomServiceAPITestCaseBase):
    def test_users(self):
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('wisdom_api:completions'))
        print("** TEST versioning: test_users ** ", r.content)
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertEqual(self.username, r.data.get('username'))

    def test_completion_request(self):
        self.client.force_authenticate(user=self.user)
        with patch.object(
            self.user,
            'date_terms_accepted',
            None,
        ):
            response = self.client.get(reverse('wisdom_api:completions'))
            print("** TEST versioning: test_completion_request ** ", response.content)

    def test_api_v0_test_endpoint(self):
        self.client.force_authenticate(user=self.user)
        with patch.object(
            self.user,
            'date_terms_accepted',
            None,
        ):
            response = self.client.get(reverse('wisdom_api:completions'))
            self.assertEqual(response.status_code, 200)

        # Make a GET request to the v1 test endpoint
        response = self.client.get(f'/api/{WISDOM_API_VERSION}/ai/completions/')

        # Assert that the response status code is 200 OK
        self.assertEqual(response.status_code, 200)

        # Assert that the response contains the expected data
        expected_data = {'message': 'This is a test'}
        self.assertEqual(response.json(), expected_data)
