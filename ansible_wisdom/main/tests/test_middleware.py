import uuid
from http import HTTPStatus
from unittest.mock import patch
from urllib.parse import urlencode

from ai.api.tests.test_views import DummyMeshClient, WisdomServiceAPITestCaseBase
from django.apps import apps
from django.test import override_settings
from django.urls import reverse
from segment import analytics


class TestMiddleware(WisdomServiceAPITestCaseBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        analytics.send = False  # do not send data to segment from unit tests

    @override_settings(ENABLE_ARI_POSTPROCESS=True)
    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_full_payload(self):
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(uuid.uuid4()),
            "metadata": {
                "documentUri": "file:///Users/username/ansible/roles/apache/tasks/main.yml",
                "activityId": str(uuid.uuid4()),
            },
        }
        response_data = {"predictions": ["      ansible.builtin.apt:\n        name: apache2"]}
        self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config('ai'),
            'model_mesh_client',
            DummyMeshClient(self, payload, response_data),
        ):
            with self.assertLogs(logger='root', level='DEBUG') as log:
                r = self.client.post(reverse('completions'), payload, format='json')
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertIsNotNone(r.data['predictions'])
                self.assertInLog("DEBUG:segment:queueing:", log.output)
                self.assertInLog("'event': 'wisdomServicePostprocessingEvent',", log.output)
                self.assertInLog("'event': 'wisdomServiceCompletionEvent',", log.output)

            with self.assertLogs(logger='root', level='DEBUG') as log:
                r = self.client.post(
                    reverse('completions'),
                    urlencode(payload),
                    content_type='application/x-www-form-urlencoded',
                )
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertIsNotNone(r.data['predictions'])
                self.assertInLog("DEBUG:segment:queueing:", log.output)
                self.assertInLog("'event': 'wisdomServicePostprocessingEvent',", log.output)
                self.assertInLog("'event': 'wisdomServiceCompletionEvent',", log.output)

            with self.assertLogs(logger='root', level='DEBUG') as log:
                r = self.client.post(
                    reverse('completions'), urlencode(payload), content_type='application/json'
                )
                self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
                self.assertInLog("DEBUG:segment:queueing:", log.output)
                self.assertNotInLog("'event': 'wisdomServicePostprocessingEvent',", log.output)
                self.assertInLog("'event': 'wisdomServiceCompletionEvent',", log.output)

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_segment_error(self):
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(uuid.uuid4()),
            "metadata": {
                "documentUri": "file:///Users/username/ansible/roles/apache/tasks/main.yml",
                "activityId": str(uuid.uuid4()),
            },
        }
        response_data = {"predictions": ["      ansible.builtin.apt:\n        name: apache2"]}
        self.client.force_authenticate(user=self.user)

        # Override properties of Segment client to cause an error
        if analytics.default_client:
            analytics.shutdown()
            analytics.default_client = None
        analytics.host = 'invalid_host_without_protocol'
        analytics.max_retries = 1
        analytics.send = True

        try:
            with patch.object(
                apps.get_app_config('ai'),
                'model_mesh_client',
                DummyMeshClient(self, payload, response_data),
            ):
                with self.assertLogs(logger='root', level='ERROR') as log:
                    r = self.client.post(reverse('completions'), payload, format='json')
                    analytics.flush()
                    self.assertEqual(r.status_code, HTTPStatus.OK)
                    self.assertIsNotNone(r.data['predictions'])
                    self.assertInLog("An error occurred in sending data to Segment: ", log.output)
        finally:
            # Restore defaults and set the 'send' flag to False during test execution
            if analytics.default_client:
                analytics.shutdown()
                analytics.default_client = None
            analytics.host = analytics.Client.DefaultConfig.host
            analytics.max_retries = analytics.Client.DefaultConfig.max_retries
            analytics.send = False
