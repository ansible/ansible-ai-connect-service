import platform
import random
import string
import time
import uuid
from ast import literal_eval
from http import HTTPStatus
from unittest.mock import patch

from ai.api.model_client.base import ModelMeshClient
from ai.api.serializers import AnsibleType, CompletionRequestSerializer, DataSource
from ai.api.tests.test_views import WisdomServiceAPITestCaseBase
from ai.api.views import Completions
from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.test import modify_settings, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITransactionTestCase
from segment import analytics
from wca.views import WCAKeyView


class TestWCAKeyView(WisdomServiceAPITestCaseBase):
    def test_authentication_error(self):
        # self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('wca', kwargs={'org_id': '1'}))
        self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)

    def test_get_unknown_org_id(self):
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('wca', kwargs={'org_id': 'unknown'}))
        self.assertEqual(r.status_code, HTTPStatus.NOT_FOUND)

    def test_get_known_org_id(self):
        self.client.force_authenticate(user=self.user)

        with patch.object(WCAKeyView, '__storage__', {'1': 'a-key'}):
            r = self.client.get(reverse('wca', kwargs={'org_id': '1'}))
            self.assertEqual(r.status_code, HTTPStatus.OK)

    def test_set_unknown_org_id(self):
        self.client.force_authenticate(user=self.user)

        # Key should initially not exist
        r = self.client.get(reverse('wca', kwargs={'org_id': '1'}))
        self.assertEqual(r.status_code, HTTPStatus.NOT_FOUND)

        # Set Key
        r = self.client.post(
            reverse('wca', kwargs={'org_id': '1'}), data='a-new-key', content_type='text/plain'
        )
        self.assertEqual(r.status_code, HTTPStatus.NO_CONTENT)

        # Check Key was stored
        r = self.client.get(reverse('wca', kwargs={'org_id': '1'}))
        self.assertEqual(r.status_code, HTTPStatus.OK)

    def test_set_known_org_id(self):
        self.client.force_authenticate(user=self.user)

        with patch.object(WCAKeyView, '__storage__', {'1': 'a-key'}):
            # Key should exist
            r = self.client.get(reverse('wca', kwargs={'org_id': '1'}))
            self.assertEqual(r.status_code, HTTPStatus.OK)

            # Set Key
            r = self.client.post(
                reverse('wca', kwargs={'org_id': '1'}), data='a-new-key', content_type='text/plain'
            )
            self.assertEqual(r.status_code, HTTPStatus.NO_CONTENT)

            # Check Key was stored
            r = self.client.get(reverse('wca', kwargs={'org_id': '1'}))
            self.assertEqual(r.status_code, HTTPStatus.OK)

    def test_delete_unknown_org_id(self):
        self.client.force_authenticate(user=self.user)
        r = self.client.delete(reverse('wca', kwargs={'org_id': '1'}))
        self.assertEqual(r.status_code, HTTPStatus.NOT_FOUND)

    def test_delete_known_org_id(self):
        self.client.force_authenticate(user=self.user)

        with patch.object(WCAKeyView, '__storage__', {'1': 'a-key'}):
            # Key should exist
            r = self.client.get(reverse('wca', kwargs={'org_id': '1'}))
            self.assertEqual(r.status_code, HTTPStatus.OK)

            r = self.client.delete(reverse('wca', kwargs={'org_id': '1'}))
            self.assertEqual(r.status_code, HTTPStatus.NO_CONTENT)

            # Check Key was removed
            r = self.client.get(reverse('wca', kwargs={'org_id': '1'}))
            self.assertEqual(r.status_code, HTTPStatus.NOT_FOUND)
