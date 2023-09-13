#!/usr/bin/env python3

import platform
import random
import string
import time
import uuid
from ast import literal_eval
from http import HTTPStatus
from unittest import mock
from unittest.mock import Mock, patch

from ai.api.model_client.base import ModelMeshClient
from ai.api.model_client.tests.test_wca_client import MockResponse
from ai.api.model_client.wca_client import WCAClient
from ai.api.serializers import AnsibleType, CompletionRequestSerializer, DataSource
from ai.api.views import Completions
from ai.feature_flags import FeatureFlags, WisdomFlags
from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.test import modify_settings, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITransactionTestCase
from segment import analytics
from test_utils import WisdomServiceLogAwareTestCase


class DummyMeshClient(ModelMeshClient):
    def __init__(self, test, payload, response_data, test_inference_match=True, has_seat=False):
        super().__init__(inference_url='dummy inference url')
        self.test = test
        self.test_inference_match = test_inference_match

        if "prompt" in payload:
            try:
                user = Mock(has_seat=has_seat)
                request = Mock(user=user)
                serializer = CompletionRequestSerializer(context={'request': request})
                data = serializer.validate(payload.copy())

                view = Completions()
                data["context"], data["prompt"], _ = view.preprocess(
                    data.get("context"), data.get("prompt")
                )

                self.expects = {
                    "instances": [
                        {
                            "context": data.get("context"),
                            "prompt": data.get("prompt"),
                            "userId": str(test.user.uuid),
                            "has_seat": has_seat,
                            "organization_id": None,
                            "suggestionId": payload.get("suggestionId"),
                        }
                    ]
                }
            except Exception as exc:  # ignore exception thrown here
                print(exc)
                pass

        self.response_data = response_data

    def infer(self, data, model_name=None):
        if self.test_inference_match:
            self.test.assertEqual(data, self.expects)
        time.sleep(0.1)  # w/o this line test_rate_limit() fails...
        # i.e., still receives 200 after 10 API calls...
        return self.response_data


class WisdomServiceAPITestCaseBase(APITransactionTestCase, WisdomServiceLogAwareTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        analytics.send = False  # do not send data to segment from unit tests

    def setUp(self):
        self.username = 'u' + "".join(random.choices(string.digits, k=5))
        self.password = 'secret'
        email = 'user@example.com'
        self.user = get_user_model().objects.create_user(
            username=self.username,
            email=email,
            password=self.password,
        )
        self.user.user_id = str(uuid.uuid4())
        self.user.community_terms_accepted = timezone.now()
        self.user.commercial_terms_accepted = timezone.now()
        self.user.save()

        group_1, _ = Group.objects.get_or_create(name='Group 1')
        group_2, _ = Group.objects.get_or_create(name='Group 2')
        group_1.user_set.add(self.user)
        group_2.user_set.add(self.user)
        cache.clear()

    def login(self):
        self.client.login(username=self.username, password=self.password)


@modify_settings()
class TestCompletionWCAView(WisdomServiceAPITestCaseBase):
    payload = {
        "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
        "suggestionId": str(uuid.uuid4()),
    }
    response_data = {"predictions": ["      ansible.builtin.apt:\n        name: apache2"]}

    @override_settings(LAUNCHDARKLY_SDK_KEY=None)
    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    @mock.patch('ai.api.views.feature_flags')
    def test_wca_featureflag_disabled(self, feature_flags):
        self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config('ai'),
            'model_mesh_client',
            DummyMeshClient(self, self.payload, self.response_data),
        ):
            r = self.client.post(reverse('completions'), self.payload)
            self.assertEqual(r.status_code, HTTPStatus.OK)
            feature_flags.assert_not_called()

    @override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    @mock.patch('ai.api.views.feature_flags')
    def test_wca_featureflag_on(self, feature_flags):
        def get_feature_flags(name, *args):
            return "https://wca_api_url<>modelX" if name == WisdomFlags.WCA_API else ""

        feature_flags.get = get_feature_flags
        self.client.force_authenticate(user=self.user)
        response = MockResponse(
            json={"predictions": [""]},
            status_code=200,
        )
        model_client = WCAClient(inference_url='https://example.com')
        model_client.session.post = Mock(return_value=response)
        model_client.get_token = Mock(return_value={"access_token": "abc"})
        with patch.object(apps.get_app_config('ai'), 'wca_client', model_client):
            r = self.client.post(reverse('completions'), self.payload)
            self.assertEqual(r.status_code, HTTPStatus.OK)
            model_client.get_token.assert_called_once()
            self.assertEqual(
                model_client.session.post.call_args.args[0],
                "https://wca_api_url/v1/wca/codegen/ansible",
            )
            self.assertEqual(
                model_client.session.post.call_args.kwargs['json']['model_id'], 'modelX'
            )

    @override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    @mock.patch('ai.api.views.feature_flags')
    def test_wca_featureflag_off(self, feature_flags):
        def get_feature_flags(name, *args):
            return None if name == WisdomFlags.WCA_API else ""

        feature_flags.get = get_feature_flags
        self.client.force_authenticate(user=self.user)
        model_client = WCAClient(inference_url='https://example.com')
        model_client.session.post = Mock()
        model_client.get_token = Mock()
        with patch.object(apps.get_app_config('ai'), 'wca_client', model_client):
            with patch.object(
                apps.get_app_config('ai'),
                'model_mesh_client',
                DummyMeshClient(self, self.payload, self.response_data),
            ):
                r = self.client.post(reverse('completions'), self.payload)
                self.assertEqual(r.status_code, HTTPStatus.OK)
                model_client.get_token.assert_not_called()
                model_client.session.post.assert_not_called()


@modify_settings()
class TestCompletionView(WisdomServiceAPITestCaseBase):
    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_full_payload(self):
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
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
                r = self.client.post(reverse('completions'), payload)
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertIsNotNone(r.data['predictions'])
                self.assertSegmentTimestamp(log)

    def test_multi_task_prompt_commercial(self):
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    # Install Apache & start Apache\n",  # noqa: E501
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {
            "predictions": [
                "- name:  Install Apache\n  ansible.builtin.apt:\n    name: apache2\n    state: latest\n- name:  start Apache\n  ansible.builtin.service:\n    name: apache2\n    state: started\n    enabled: yes\n"  # noqa: E501
            ]
        }
        self.user.has_seat = True
        self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config('ai'),
            'model_mesh_client',
            DummyMeshClient(self, payload, response_data, has_seat=True),
        ):
            with self.assertLogs(logger='root', level='DEBUG') as log:
                r = self.client.post(reverse('completions'), payload)
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertIsNotNone(r.data['predictions'])
                self.assertSegmentTimestamp(log)

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_rate_limit(self):
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
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
                r = self.client.post(reverse('completions'), payload)
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertIsNotNone(r.data['predictions'])
                for _ in range(10):
                    r = self.client.post(reverse('completions'), payload)
                self.assertEqual(r.status_code, HTTPStatus.TOO_MANY_REQUESTS)
                self.assertSegmentTimestamp(log)

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_missing_prompt(self):
        payload = {
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
                r = self.client.post(reverse('completions'), payload)
                self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
                self.assertSegmentTimestamp(log)

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_authentication_error(self):
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {"predictions": ["      ansible.builtin.apt:\n        name: apache2"]}
        # self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config('ai'),
            'model_mesh_client',
            DummyMeshClient(self, payload, response_data),
        ):
            with self.assertLogs(logger='root', level='DEBUG') as log:
                r = self.client.post(reverse('completions'), payload)
                self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)
                segment_events = self.extractSegmentEventsFromLog(log)
                self.assertTrue(len(segment_events) > 0)
                for event in segment_events:
                    self.assertEqual(event['userId'], 'unknown')
                    properties = event['properties']
                    self.assertTrue('modelName' in properties)
                    self.assertTrue('imageTags' in properties)
                    self.assertEqual(properties['response']['status_code'], 401)
                    self.assertIsNotNone(event['timestamp'])

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_completions_preprocessing_error(self):
        payload = {
            "prompt": "---\n- hosts: all\nbecome: yes\n\n  tasks:\n    - name: Install Apache\n",
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
                r = self.client.post(reverse('completions'), payload)
                self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
                self.assertEqual(r.data['message'], 'Request contains invalid yaml')
                self.assertSegmentTimestamp(log)

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_completions_preprocessing_error_with_invalid_prompt(self):
        payload = {
            "prompt": "---\n  - name: [Setup]",
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
                r = self.client.post(reverse('completions'), payload)
                self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
                self.assertEqual(r.data['message'], 'Request contains invalid prompt')
                self.assertSegmentTimestamp(log)

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_completions_preprocessing_error_without_name_prompt(self):
        payload = {
            "prompt": "---\n  - Name: [Setup]",
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
                r = self.client.post(reverse('completions'), payload)
                self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
                self.assertInLog("failed to validate request", log)
                self.assertTrue("prompt does not contain the name parameter" in str(r.content))
                self.assertSegmentTimestamp(log)

    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_full_payload_without_ARI(self):
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
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
                r = self.client.post(reverse('completions'), payload)
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertIsNotNone(r.data['predictions'])
                self.assertInLog('skipped ari post processing because ari was not initialized', log)
                self.assertSegmentTimestamp(log)

    @override_settings(ENABLE_ARI_POSTPROCESS=True)
    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_full_payload_with_recommendation_with_broken_last_line(self):
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(uuid.uuid4()),
        }
        # quotation in the last line is not closed, but the truncate function can handle this.
        response_data = {
            "predictions": [
                "      ansible.builtin.apt:\n        name: apache2\n      register: \"test"
            ]
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger='root', level='INFO') as log:
            with patch.object(
                apps.get_app_config('ai'),
                'model_mesh_client',
                DummyMeshClient(self, payload, response_data),
            ):
                r = self.client.post(reverse('completions'), payload)
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertIsNotNone(r.data['predictions'])
                self.assertNotInLog('the recommendation_yaml is not a valid YAML', log)
                self.assertSegmentTimestamp(log)

    @override_settings(ENABLE_ARI_POSTPROCESS=True)
    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_completions_postprocessing_error_for_invalid_yaml(self):
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(uuid.uuid4()),
        }
        # this prediction has indentation problem with the prompt above
        response_data = {
            "predictions": ["      ansible.builtin.apt:\n garbage       name: apache2"]
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger='root', level='ERROR') as log:  # Suppress debug output
            with patch.object(
                apps.get_app_config('ai'),
                'model_mesh_client',
                DummyMeshClient(self, payload, response_data),
            ):
                r = self.client.post(reverse('completions'), payload)
                self.assertEqual(HTTPStatus.NO_CONTENT, r.status_code)
                self.assertEqual(None, r.data)
                self.assertInLog('error postprocessing prediction for suggestion', log)
                self.assertSegmentTimestamp(log)

    @override_settings(ENABLE_ARI_POSTPROCESS=True)
    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_completions_postprocessing_for_invalid_suggestion(self):
        # the suggested task is a invalid because it does not have module name
        # in this case, ARI should throw an exception
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(uuid.uuid4()),
        }
        # module name in the prediction is ""
        response_data = {"predictions": ["      \"\":\n        name: apache2"]}
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(
            logger='root', level='DEBUG'
        ) as log:  # Enable debug outputs for getting Segment events
            with patch.object(
                apps.get_app_config('ai'),
                'model_mesh_client',
                DummyMeshClient(self, payload, response_data),
            ):
                r = self.client.post(reverse('completions'), payload)
                self.assertEqual(HTTPStatus.NO_CONTENT, r.status_code)
                self.assertEqual(None, r.data)
                self.assertInLog('error postprocessing prediction for suggestion', log)
                segment_events = self.extractSegmentEventsFromLog(log)
                self.assertTrue(len(segment_events) > 0)
                for event in segment_events:
                    if event['event'] == 'postprocess':
                        self.assertEqual(
                            'ARI rule evaluation threw fatal exception: '
                            'Invalid task structure: no module name found',
                            event['properties']['problem'],
                        )
                    self.assertIsNotNone(event['timestamp'])

    @override_settings(ENABLE_ANSIBLE_LINT_POSTPROCESS=True)
    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    def test_payload_with_ansible_lint(self):
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {"predictions": ["      ansible.builtin.apt:\n        name: apache2"]}
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger='root', level='WARN') as log:
            with patch.object(
                apps.get_app_config('ai'),
                'model_mesh_client',
                DummyMeshClient(self, payload, response_data),
            ):
                r = self.client.post(reverse('completions'), payload)
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertIsNotNone(r.data['predictions'])

    @override_settings(ENABLE_ANSIBLE_LINT_POSTPROCESS=False)
    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    def test_full_payload_without_ansible_lint_without_commercial(self):
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
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
                r = self.client.post(reverse('completions'), payload)
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertIsNotNone(r.data['predictions'])
                self.assertInLog(
                    'skipped ansible lint post processing as lint processing is allowed'
                    ' for Commercial Users only!',
                    log,
                )
                self.assertSegmentTimestamp(log)

    @override_settings(ENABLE_ANSIBLE_LINT_POSTPROCESS=False)
    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    def test_full_payload_without_ansible_lint_with_commercial_user(self):
        self.user.has_seat = True
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {"predictions": ["      ansible.builtin.apt:\n        name: apache2"]}
        self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config('ai'),
            'model_mesh_client',
            DummyMeshClient(self, payload, response_data, has_seat=True),
        ):
            with self.assertLogs(logger='root', level='DEBUG') as log:
                r = self.client.post(reverse('completions'), payload)
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertIsNotNone(r.data['predictions'])
                self.assertSegmentTimestamp(log)

    @override_settings(ENABLE_ANSIBLE_LINT_POSTPROCESS=True)
    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    @override_settings(ENABLE_ARI_POSTPROCESS=False)
    def test_full_payload_with_ansible_lint_with_commercial_user(self):
        self.user.has_seat = True
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {"predictions": ["      ansible.builtin.apt:\n        name: apache2"]}
        self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config('ai'),
            'model_mesh_client',
            DummyMeshClient(self, payload, response_data, has_seat=True),
        ):
            with self.assertLogs(logger='root', level='DEBUG') as log:
                r = self.client.post(reverse('completions'), payload)
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertIsNotNone(r.data['predictions'])
                self.assertSegmentTimestamp(log)

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_completions_pii_clean_up(self):
        payload = {
            "prompt": "- name: Create an account for foo@ansible.com \n",
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {"predictions": [""]}
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger='root', level='DEBUG') as log:
            with patch.object(
                apps.get_app_config('ai'),
                'model_mesh_client',
                DummyMeshClient(self, payload, response_data, False),
            ):
                self.client.post(reverse('completions'), payload)
                self.assertInLog('Create an account for james8@example.com', log)
                self.assertSegmentTimestamp(log)

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_full_completion_post_response(self):
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(uuid.uuid4()),
        }
        response_data = {
            "predictions": ["      ansible.builtin.apt:\n        name: apache2"],
        }
        self.client.force_authenticate(user=self.user)
        with patch.object(
            apps.get_app_config('ai'),
            'model_mesh_client',
            DummyMeshClient(self, payload, response_data),
        ):
            with self.assertLogs(logger='root', level='DEBUG') as log:
                r = self.client.post(reverse('completions'), payload)
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertIsNotNone(r.data['predictions'])
                self.assertIsNotNone(r.data['modelName'])
                self.assertIsNotNone(r.data['suggestionId'])
                self.assertSegmentTimestamp(log)


@modify_settings()
class TestFeedbackView(WisdomServiceAPITestCaseBase):
    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_feedback_full_payload(self):
        payload = {
            "inlineSuggestion": {
                "latency": 1000,
                "userActionTime": 3500,
                "documentUri": "file:///home/user/ansible.yaml",
                "action": "0",
                "suggestionId": str(uuid.uuid4()),
            },
            "ansibleContent": {
                "content": "---\n- hosts: all\n  become: yes\n\n  "
                "tasks:\n    - name: Install Apache\n",
                "documentUri": "file:///home/user/ansible.yaml",
                "activityId": str(uuid.uuid4()),
                "trigger": "0",
            },
            "sentimentFeedback": {
                "value": 4,
                "feedback": "This is a test feedback",
            },
            "suggestionQualityFeedback": {
                "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n"
                " - name: Install Apache\n",
                "providedSuggestion": "    when: ansible_os_family == 'Debian'\n    "
                "ansible.builtin.package:\n      name: apache2\n"
                "      state: present",
                "expectedSuggestion": "    when: ansible_os_family == 'Debian'\n    "
                "ansible.builtin.package:\n      name: apache\n"
                "      state: present",
                "additionalComment": "Package name is changed",
            },
            "issueFeedback": {
                "type": "bug-report",
                "title": "This is a test issue",
                "description": "This is a test issue description",
            },
        }
        with self.assertLogs(logger='root', level='DEBUG') as log:
            self.client.force_authenticate(user=self.user)
            r = self.client.post(reverse('feedback'), payload, format='json')
            self.assertEqual(r.status_code, HTTPStatus.OK)
            self.assertSegmentTimestamp(log)

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_missing_content(self):
        payload = {
            "ansibleContent": {"documentUri": "file:///home/user/ansible.yaml", "trigger": "0"}
        }
        with self.assertLogs(logger='root', level='DEBUG') as log:
            self.client.force_authenticate(user=self.user)
            r = self.client.post(reverse('feedback'), payload, format="json")
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            self.assertSegmentTimestamp(log)

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_anonymize(self):
        payload = {
            "ansibleContent": {
                "content": "---\n- hosts: all\n  become: yes\n\n  "
                "tasks:\n    - name: Install Apache\n",
                "documentUri": "file:///home/jean-pierre/ansible.yaml",
                "trigger": "0",
            }
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger='root', level='DEBUG') as log:
            r = self.client.post(reverse('feedback'), payload, format="json")
            self.assertNotInLog('file:///home/user/ansible.yaml', log)
            self.assertInLog('file:///home/ano-user/ansible.yaml', log)
            self.assertSegmentTimestamp(log)

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_authentication_error(self):
        payload = {
            "ansibleContent": {
                "content": "---\n- hosts: all\n  become: yes\n\n  "
                "tasks:\n    - name: Install Apache\n",
                "documentUri": "file:///home/user/ansible.yaml",
                "trigger": "0",
            }
        }
        # self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger='root', level='DEBUG') as log:
            r = self.client.post(reverse('feedback'), payload, format="json")
            self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)
            self.assertSegmentTimestamp(log)

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_feedback_segment_events(self):
        payload = {
            "inlineSuggestion": {
                "latency": 1000,
                "userActionTime": 3500,
                "documentUri": "file:///home/user/ansible.yaml",
                "action": "0",
                "suggestionId": str(uuid.uuid4()),
            },
            "ansibleContent": {
                "content": "---\n- hosts: all\n  become: yes\n\n  "
                "tasks:\n    - name: Install Apache\n",
                "documentUri": "file:///home/user/ansible.yaml",
                "activityId": str(uuid.uuid4()),
                "trigger": "0",
            },
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger='root', level='DEBUG') as log:
            r = self.client.post(reverse('feedback'), payload, format='json')
            self.assertEqual(r.status_code, HTTPStatus.OK)

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
                self.assertIsNotNone(event['timestamp'])

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_feedback_segment_inline_suggestion_feedback_error(self):
        payload = {
            "inlineSuggestion": {
                "latency": 1000,
                "userActionTime": 3500,
                "documentUri": "file:///home/rbobbitt/ansible.yaml",
                "action": "2",  # invalid choice for action
                "suggestionId": str(uuid.uuid4()),
            }
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger='root', level='DEBUG') as log:
            r = self.client.post(reverse('feedback'), payload, format='json')
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)

            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertTrue(len(segment_events) > 0)
            for event in segment_events:
                self.assertTrue('inlineSuggestionFeedback', event['event'])
                properties = event['properties']
                self.assertTrue('data' in properties)
                self.assertTrue('exception' in properties)
                self.assertEqual(
                    "file:///home/ano-user/ansible.yaml",
                    properties['data']['inlineSuggestion']['documentUri'],
                )
                self.assertIsNotNone(event['timestamp'])

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_feedback_segment_ansible_content_feedback_error(self):
        payload = {
            "ansibleContent": {
                "content": "---\n- hosts: all\n  become: yes\n\n  "
                "tasks:\n    - name: Install Apache\n",
                "documentUri": "file:///home/rbobbitt/ansible.yaml",
                "activityId": "123456",  # an invalid UUID
                "trigger": "0",
            }
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger='root', level='DEBUG') as log:
            r = self.client.post(reverse('feedback'), payload, format='json')
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)

            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertTrue(len(segment_events) > 0)
            for event in segment_events:
                self.assertTrue('ansibleContentFeedback', event['event'])
                properties = event['properties']
                self.assertTrue('data' in properties)
                self.assertTrue('exception' in properties)
                self.assertEqual(
                    "file:///home/ano-user/ansible.yaml",
                    properties['data']['ansibleContent']['documentUri'],
                )
                self.assertIsNotNone(event['timestamp'])

    @patch('ai.api.serializers.FeedbackRequestSerializer.is_valid')
    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_feedback_segment_ansible_content_500_error(self, is_valid):
        is_valid.side_effect = Exception('Dummy Exception')
        payload = {
            "ansibleContent": {
                "content": "---\n- hosts: all\n  become: yes\n\n  "
                "tasks:\n    - name: Install Apache\n",
                "documentUri": "file:///home/rbobbitt/ansible.yaml",
                "activityId": str(uuid.uuid4()),
                "trigger": "0",
            }
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger='root', level='DEBUG') as log:
            r = self.client.post(reverse('feedback'), payload, format='json')
            self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
            self.assertInLog("An exception <class 'Exception'> occurred in sending a feedback", log)
            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertTrue(len(segment_events) > 0)
            for event in segment_events:
                self.assertTrue('ansibleContentFeedback', event['event'])
                properties = event['properties']
                self.assertTrue('data' in properties)
                self.assertTrue('exception' in properties)
                self.assertEqual('Dummy Exception', properties['exception'])
                self.assertEqual(
                    "file:///home/ano-user/ansible.yaml",
                    properties['data']['ansibleContent']['documentUri'],
                )
                self.assertIsNotNone(event['timestamp'])

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_feedback_segment_suggestion_quality_feedback_error(self):
        payload = {
            "suggestionQualityFeedback": {
                # required key "prompt" is missing
                "providedSuggestion": "    when: ansible_os_family == 'Debian'\n    "
                "ansible.builtin.package:\n      name: apache2\n      "
                "state: present",
                "expectedSuggestion": "    when: ansible_os_family == 'Debian'\n    "
                "ansible.builtin.package:\n      name: apache\n      "
                "state: present",
                "additionalComment": "Package name is changed",
            }
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger='root', level='DEBUG') as log:
            r = self.client.post(reverse('feedback'), payload, format='json')
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)

            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertTrue(len(segment_events) > 0)
            for event in segment_events:
                self.assertTrue('suggestionQualityFeedback', event['event'])
                properties = event['properties']
                self.assertTrue('data' in properties)
                self.assertTrue('exception' in properties)
                self.assertEqual(
                    "Package name is changed",
                    properties['data']['suggestionQualityFeedback']['additionalComment'],
                )
                self.assertIsNotNone(event['timestamp'])

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_feedback_segment_sentiment_feedback_error(self):
        payload = {
            "sentimentFeedback": {
                # missing required key "value"
                "feedback": "This is a test feedback",
            }
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger='root', level='DEBUG') as log:
            r = self.client.post(reverse('feedback'), payload, format='json')
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)

            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertTrue(len(segment_events) > 0)
            for event in segment_events:
                self.assertTrue('suggestionQualityFeedback', event['event'])
                properties = event['properties']
                self.assertTrue('data' in properties)
                self.assertTrue('exception' in properties)
                self.assertEqual(
                    "This is a test feedback",
                    properties['data']['sentimentFeedback']['feedback'],
                )
                self.assertIsNotNone(event['timestamp'])

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_feedback_segment_issue_feedback_error(self):
        payload = {
            "issueFeedback": {
                "type": "bug-report",
                # missing required key "title"
                "description": "This is a test description",
            }
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger='root', level='DEBUG') as log:
            r = self.client.post(reverse('feedback'), payload, format='json')
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)

            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertTrue(len(segment_events) > 0)
            for event in segment_events:
                self.assertTrue('issueFeedback', event['event'])
                properties = event['properties']
                self.assertTrue('data' in properties)
                self.assertTrue('exception' in properties)
                self.assertEqual(
                    "This is a test description",
                    properties['data']['issueFeedback']['description'],
                )
                self.assertIsNotNone(event['timestamp'])


class TestAttributionsView(WisdomServiceAPITestCaseBase):
    @patch('ai.search.search')
    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_segment_events(self, mock_search):
        mock_search.return_value = {
            'attributions': [
                {
                    'repo_name': 'repo_name',
                    'repo_url': 'http://example.com',
                    'path': '/path',
                    'license': 'license',
                    'data_source': DataSource.UNKNOWN,
                    'ansible_type': AnsibleType.UNKNOWN,
                    'score': 0.0,
                },
            ],
            'meta': {
                'encode_duration': 1000,
                'search_duration': 2000,
            },
        }
        payload = {
            'suggestion': 'suggestion',
            'suggestionId': str(uuid.uuid4()),
        }

        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger='root', level='DEBUG') as log:
            r = self.client.post(reverse('attributions'), payload, format='json')
            self.assertEqual(r.status_code, HTTPStatus.OK)

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
                self.assertIsNotNone(event['timestamp'])

    @patch('ai.search.search')
    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_segment_events_with_exception(self, mock_search):
        mock_search.side_effect = Exception('Search Exception')
        payload = {
            'suggestion': 'suggestion',
            'suggestionId': str(uuid.uuid4()),
        }

        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger='root', level='DEBUG') as log:
            r = self.client.post(reverse('attributions'), payload, format='json')
            self.assertEqual(r.status_code, HTTPStatus.SERVICE_UNAVAILABLE)

            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertEqual(len(segment_events), 0)
            self.assertInLog('Failed to search for attributions', log)
