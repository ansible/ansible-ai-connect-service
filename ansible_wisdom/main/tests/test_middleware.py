import os.path
import platform
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
                self.assertInLog("DEBUG:segment:queueing:", log)
                self.assertInLog("'event': 'prediction',", log)
                self.assertInLog("'event': 'postprocess',", log)
                self.assertInLog("'event': 'completion',", log)
                self.assertNotInLog("foo@ansible.com", log)
                self.assertNotInLog("username", log)
                self.assertInLog("james8@example.com", log)
                self.assertInLog("ano-user", log)

                segment_events = self.extractSegmentEventsFromLog(log)
                self.assertTrue(len(segment_events) > 0)
                hostname = platform.node()
                for event in segment_events:
                    properties = event['properties']
                    self.assertTrue('modelName' in properties)
                    self.assertTrue('imageTags' in properties)
                    self.assertTrue('groups' in properties)
                    self.assertTrue('Group 1' in properties['groups'])
                    self.assertTrue('Group 2' in properties['groups'])
                    self.assertEqual(hostname, properties['hostname'])
                    if event['event'] == 'completion':
                        self.assertEqual('ansible.builtin.package', properties['module'])
                        self.assertEqual('ansible.builtin', properties['collection'])
                    self.assertIsNotNone(event['timestamp'])

            with self.assertLogs(logger='root', level='DEBUG') as log:
                r = self.client.post(
                    reverse('completions'),
                    urlencode(payload),
                    content_type='application/x-www-form-urlencoded',
                )
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertIsNotNone(r.data['predictions'])
                self.assertInLog("DEBUG:segment:queueing:", log)
                self.assertInLog("'event': 'prediction',", log)
                self.assertInLog("'event': 'postprocess',", log)
                self.assertInLog("'event': 'completion',", log)
                self.assertNotInLog("foo@ansible.com", log)
                self.assertNotInLog("username", log)
                self.assertInLog("james8@example.com", log)
                self.assertInLog("ano-user", log)
                self.assertSegmentTimestamp(log)

            with self.assertLogs(logger='root', level='DEBUG') as log:
                r = self.client.post(
                    reverse('completions'), urlencode(payload), content_type='application/json'
                )
                self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
                self.assertInLog("DEBUG:segment:queueing:", log)
                self.assertNotInLog("'event': 'prediction',", log)
                self.assertNotInLog("'event': 'postprocess',", log)
                self.assertInLog("'event': 'completion',", log)
                self.assertNotInLog("foo@ansible.com", log)
                self.assertNotInLog("username", log)
                self.assertSegmentTimestamp(log)

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    @patch('ai.api.views.fmtr.preprocess', side_effect=Exception)
    def test_preprocess_error(self, preprocess):
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n"
            "    - name: Install Apache for foo@ansible.com\n",
        }

        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger='root', level='DEBUG') as log:
            self.client.post(reverse('completions'), payload, format='json')
            self.assertInLog("ERROR:ai.api.views:failed to preprocess:", log)
            self.assertSegmentTimestamp(log)

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
                with self.assertLogs(logger='root', level='DEBUG') as log:
                    r = self.client.post(reverse('completions'), payload, format='json')
                    analytics.flush()
                    self.assertEqual(r.status_code, HTTPStatus.OK)
                    self.assertIsNotNone(r.data['predictions'])
                    self.assertInLog("An error occurred in sending data to Segment: ", log)
                    self.assertSegmentTimestamp(log)
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
                self.client.post(reverse('completions'), payload, format='json')
                analytics.flush()
                self.assertInLog("Message exceeds 32kb limit. msg_len=", log)
                self.assertInLog("sent segment event: segmentError", log)
                events = self.extractSegmentEventsFromLog(log)
                n = len(events)
                self.assertTrue(n > 0)
                self.assertEqual(events[n - 1]['properties']['error_type'], 'event_exceeds_limit')
                self.assertIsNotNone(events[n - 1]['properties']['details']['event_name'])
                self.assertIsNotNone(events[n - 1]['properties']['details']['msg_len'] > 32 * 1024)
                self.assertSegmentTimestamp(log)
