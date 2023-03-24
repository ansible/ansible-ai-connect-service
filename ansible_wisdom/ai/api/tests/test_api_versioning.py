from http import HTTPStatus
from unittest.mock import patch

from django.shortcuts import reverse

from .test_views import WisdomServiceAPITestCaseBase


class TestAPIVersioning(WisdomServiceAPITestCaseBase):
    def test_users_api_endpoint(self):
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('wisdom_users:me'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertEqual(self.username, r.data.get('username'))
