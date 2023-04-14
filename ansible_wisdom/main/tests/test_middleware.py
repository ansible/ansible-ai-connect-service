import os.path
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
        suggestionId = str(uuid.uuid4())
        activityId = str(uuid.uuid4())

        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n"
            "    - name: Install Apache for foo@ansible.com\n",
            "suggestionId": suggestionId,
            "metadata": {
                "documentUri": "file:///Users/username/ansible/roles/apache/tasks/main.yml",
                "activityId": activityId,
            },
        }
        expected = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n"
            "    - name: Install Apache for james8@example.com\n",
            "suggestionId": suggestionId,
            "metadata": {
                "documentUri": "file:///Users/ano-user/ansible/roles/apache/tasks/main.yml",
                "activityId": activityId,
            },
        }
        response_data = {"predictions": ["      ansible.builtin.apt:\n        name: apache2"]}
        self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config('ai'),
            'model_mesh_client',
            DummyMeshClient(self, expected, response_data),
        ):
            with self.assertLogs(logger='root', level='DEBUG') as log:
                r = self.client.post(reverse('completions'), payload, format='json')
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertIsNotNone(r.data['predictions'])
                self.assertInLog("DEBUG:segment:queueing:", log.output)
                self.assertInLog("'event': 'prediction',", log.output)
                self.assertInLog("'event': 'postprocess',", log.output)
                self.assertInLog("'event': 'completion',", log.output)
                self.assertNotInLog("foo@ansible.com", log.output)
                self.assertNotInLog("username", log.output)
                self.assertInLog("james8@example.com", log.output)
                self.assertInLog("ano-user", log.output)

                segment_events = self.extractSegmentEventsFromLog(log.output)
                self.assertTrue(len(segment_events) > 0)
                for event in segment_events:
                    self.assertTrue('modelName' in event)
                    self.assertTrue('imageTags' in event)

            with self.assertLogs(logger='root', level='DEBUG') as log:
                r = self.client.post(
                    reverse('completions'),
                    urlencode(payload),
                    content_type='application/x-www-form-urlencoded',
                )
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertIsNotNone(r.data['predictions'])
                self.assertInLog("DEBUG:segment:queueing:", log.output)
                self.assertInLog("'event': 'prediction',", log.output)
                self.assertInLog("'event': 'postprocess',", log.output)
                self.assertInLog("'event': 'completion',", log.output)
                self.assertNotInLog("foo@ansible.com", log.output)
                self.assertNotInLog("username", log.output)
                self.assertInLog("james8@example.com", log.output)
                self.assertInLog("ano-user", log.output)

            with self.assertLogs(logger='root', level='DEBUG') as log:
                r = self.client.post(
                    reverse('completions'), urlencode(payload), content_type='application/json'
                )
                self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
                self.assertInLog("DEBUG:segment:queueing:", log.output)
                self.assertNotInLog("'event': 'prediction',", log.output)
                self.assertNotInLog("'event': 'postprocess',", log.output)
                self.assertInLog("'event': 'completion',", log.output)
                self.assertNotInLog("foo@ansible.com", log.output)
                self.assertNotInLog("username", log.output)

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

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_segment_error_with_data_exceeding_limit(self):
        prompt = '''---
- hosts: localhost
  connection: local

  tasks:
'''
        prompt += (
            '''
    - name: Create x

      amazon.aws.ec2_vpc_net:
        state: present
        name: "{{ vpc_name }}"
        cidr_block: "{{ cidr_block }}"
        region: "{{ region }}"
        access_key: "{{ access_key }}"
        secret_key: "{{ secret_key }}"
        tags:
          tag-name: tag-value
      register: ec2_vpc_net
'''
            * 100
        )

        prompt += '\n    - name: Create x\n'

        payload = {
            "prompt": prompt,
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
                analytics.flush()
                self.assertInLog("Message exceeds 32kb limit. msg_len=", log.output)
                self.assertInLog("sent segment event: segmentError", log.output)
                events = self.extractSegmentEventsFromLog(log.output)
                n = len(events)
                self.assertTrue(n > 0)
                self.assertEqual(events[n - 1]['error_type'], 'event_exceeds_limit')
                self.assertIsNotNone(events[n - 1]['details']['event_name'])
                self.assertIsNotNone(events[n - 1]['details']['msg_len'] > 32 * 1024)
