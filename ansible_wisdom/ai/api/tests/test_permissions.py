from http import HTTPStatus
from unittest.mock import patch

from django.apps import apps
from django.test import override_settings
from django.urls import reverse
from requests.exceptions import ReadTimeout

from .test_views import WisdomServiceAPITestCaseBase

WISDOM_API_VERSION = "v0"


class AcceptedTermsPermissionTest(WisdomServiceAPITestCaseBase):
    def test_user_has_not_accepted(self):
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
        }
        with patch.object(
            self.user,
            'date_terms_accepted',
            None,
        ):
            self.client.force_authenticate(user=self.user)
            r = self.client.post(reverse('wisdom_api:completions'), payload)
        self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
