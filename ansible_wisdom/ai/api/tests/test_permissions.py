from http import HTTPStatus
from unittest.mock import patch

from django.apps import apps
from django.test import override_settings
from django.urls import reverse
from requests.exceptions import ReadTimeout

from .test_views import WisdomServiceAPITestCaseBase


class AcceptedTermsPermissionTest(WisdomServiceAPITestCaseBase):
    def test_user_has_accepted(self):
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
        }
        self.assertIsNotNone(self.user.date_terms_accepted)
        self.client.force_authenticate(user=self.user)
        r = self.client.post(reverse('completions'), payload)
        self.assertEqual(r.status_code, HTTPStatus.OK)

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
            r = self.client.post(reverse('completions'), payload)
        self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)

    def test_superuser_has_not_accepted(self):
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
        }
        with patch.object(
            self.user,
            'date_terms_accepted',
            None,
        ), patch.object(
            self.user,
            'is_superuser',
            True,
        ):
            self.client.force_authenticate(user=self.user)
            r = self.client.post(reverse('completions'), payload)
        self.assertEqual(r.status_code, HTTPStatus.OK)
