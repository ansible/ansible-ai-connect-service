import json
import sys
import uuid
from unittest.mock import patch
from urllib.parse import urlencode

from ai.api.tests.test_views import DummyMeshClient, WisdomServiceAPITestCaseBase
from django.apps import apps
from django.test import override_settings
from segment import analytics


class TestMiddleware(WisdomServiceAPITestCaseBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        analytics.send = False  # do not send data to segment from unit tests

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_full_payload(self):
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "userId": self.user_id,
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {"predictions": ["      ansible.builtin.apt:\n        name: apache2"]}
        self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config('ai'),
            'model_mesh_client',
            DummyMeshClient(self, payload, response_data),
        ):
            with self.assertLogs(logger='root', level='DEBUG') as log:
                r = self.client.post('/api/ai/completions/', payload)
                self.assertEqual(r.status_code, 200)
                self.assertIsNotNone(r.data['predictions'])
                self.assertInLog("DEBUG:segment:queueing:", log.output)
                self.assertInLog("'event': 'wisdomServicePostprocessingEvent',", log.output)
                self.assertInLog("'event': 'wisdomServiceCompletionEvent',", log.output)

            with self.assertLogs(logger='root', level='DEBUG') as log:
                r = self.client.post(
                    '/api/ai/completions/',
                    urlencode(payload),
                    content_type='application/x-www-form-urlencoded',
                )
                self.assertEqual(r.status_code, 200)
                self.assertIsNotNone(r.data['predictions'])
                self.assertInLog("DEBUG:segment:queueing:", log.output)
                self.assertInLog("'event': 'wisdomServicePostprocessingEvent',", log.output)
                self.assertInLog("'event': 'wisdomServiceCompletionEvent',", log.output)

            with self.assertLogs(logger='root', level='DEBUG') as log:
                r = self.client.post(
                    '/api/ai/completions/', urlencode(payload), content_type='application/json'
                )
                self.assertEqual(r.status_code, 400)
                self.assertInLog("DEBUG:segment:queueing:", log.output)
                self.assertNotInLog("'event': 'wisdomServicePostprocessingEvent',", log.output)
                self.assertInLog("'event': 'wisdomServiceCompletionEvent',", log.output)
