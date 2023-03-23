from http import HTTPStatus
from unittest.mock import patch

from django.apps import apps
from django.test import override_settings
from django.urls import reverse
from requests.exceptions import ReadTimeout

from .test_views import WisdomServiceAPITestCaseBase


class AcceptedTermsPermission(WisdomServiceAPITestCaseBase):
    @override_settings(OAUTH2_ENABLE=1)
    def test_user_has_not_accepted(self):
        self.client.force_authenticate(user=self.user)
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
        }
        r = self.client.post(reverse('completions'), payload)
        self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)
