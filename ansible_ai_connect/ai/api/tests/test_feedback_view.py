#!/usr/bin/env python3

#  Copyright Red Hat
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
import logging
import platform
import uuid
from http import HTTPStatus
from unittest.mock import Mock, patch

from django.apps import apps
from django.test import modify_settings, override_settings

from ansible_ai_connect.ai.api.exceptions import FeedbackValidationException
from ansible_ai_connect.ai.api.model_pipelines.exceptions import (
    WcaModelIdNotFound,
    WcaNoDefaultModelId,
)
from ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_saas import (
    WCASaaSCompletionsPipeline,
)
from ansible_ai_connect.organizations.models import ExternalOrganization
from ansible_ai_connect.test_utils import (
    APIVersionTestCaseBase,
    WisdomServiceAPITestCaseBase,
)

logger = logging.getLogger(__name__)


@modify_settings()
@override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
class TestFeedbackView(APIVersionTestCaseBase, WisdomServiceAPITestCaseBase):

    VALID_PAYLOAD_WITH_CONVERSATION_ID = {
        "query": "Hello",
        "conversation_id": "123e4567-e89b-12d3-a456-426614174000",
    }

    def setUp(self):
        super().setUp()
        (org, _) = ExternalOrganization.objects.get_or_create(id=123, telemetry_opt_out=False)
        self.user.organization = org

    def test_feedback_full_payload(self):
        payload = {
            "inlineSuggestion": {
                "userActionTime": 3500,
                "documentUri": "file:///home/user/ansible.yaml",
                "action": "0",
                "suggestionId": str(uuid.uuid4()),
            },
            "ansibleContent": {
                "content": "---\n- hosts: all\n  become: yes\n\n  "
                "tasks:\n    - name: Install Apache\n",
                "documentUri": "file:///home/user/ansible.yaml",
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
            "model": str(uuid.uuid4()),
        }
        with self.assertLogs(logger="root", level="DEBUG") as log:
            self.client.force_authenticate(user=self.user)
            r = self.client.post(self.api_version_reverse("feedback"), payload, format="json")
            self.assertEqual(r.status_code, HTTPStatus.OK)
            self.assertSegmentTimestamp(log)

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
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(self.api_version_reverse("feedback"), payload, format="json")
            self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)
            self.assertSegmentTimestamp(log)

    def test_feedback_segment_events(self):
        payload = {
            "inlineSuggestion": {
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
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(self.api_version_reverse("feedback"), payload, format="json")
            self.assertEqual(r.status_code, HTTPStatus.OK)

            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertTrue(len(segment_events) > 0)
            hostname = platform.node()
            for event in segment_events:
                properties = event["properties"]
                self.assertTrue("modelName" in properties)
                self.assertTrue("imageTags" in properties)
                self.assertTrue("groups" in properties)
                self.assertTrue("Group 1" in properties["groups"])
                self.assertTrue("Group 2" in properties["groups"])
                self.assertTrue("rh_user_has_seat" in properties)
                self.assertTrue("rh_user_org_id" in properties)
                self.assertEqual(hostname, properties["hostname"])
                self.assertIsNotNone(event["timestamp"])

    def test_feedback_segment_events_with_custom_model(self):
        model_name = str(uuid.uuid4())
        payload = {
            "inlineSuggestion": {
                "userActionTime": 3500,
                "documentUri": "file:///home/user/ansible.yaml",
                "action": "0",
                "suggestionId": str(uuid.uuid4()),
            },
            "model": model_name,
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(self.api_version_reverse("feedback"), payload, format="json")
            self.assertEqual(r.status_code, HTTPStatus.OK)

            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertTrue(len(segment_events) > 0)
            for event in segment_events:
                properties = event["properties"]
                self.assertTrue("modelName" in properties)
                self.assertEqual(model_name, properties["modelName"])

    def test_feedback_segment_events_user_not_linked_to_org_error(self):
        model_client = Mock(WCASaaSCompletionsPipeline)
        model_client.get_model_id.side_effect = WcaNoDefaultModelId()

        payload = {
            "inlineSuggestion": {
                "userActionTime": 3500,
                "documentUri": "file:///home/user/ansible.yaml",
                "action": "0",
                "suggestionId": str(uuid.uuid4()),
            },
        }
        self.client.force_authenticate(user=self.user)

        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(self.api_version_reverse("feedback"), payload, format="json")
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertInLog("Failed to retrieve Model Name for Feedback.", log)
                self.assertInLog("Org ID: 123", log)

                segment_events = self.extractSegmentEventsFromLog(log)
                self.assertTrue(len(segment_events) > 0)
                for event in segment_events:
                    properties = event["properties"]
                    self.assertTrue("modelName" in properties)
                    self.assertEqual("", properties["modelName"])

    def test_feedback_segment_events_model_name_error(self):
        model_client = Mock(WCASaaSCompletionsPipeline)
        model_client.get_model_id.side_effect = WcaModelIdNotFound()

        payload = {
            "inlineSuggestion": {
                "userActionTime": 3500,
                "documentUri": "file:///home/user/ansible.yaml",
                "action": "0",
                "suggestionId": str(uuid.uuid4()),
            },
        }
        self.client.force_authenticate(user=self.user)

        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(self.api_version_reverse("feedback"), payload, format="json")
                self.assertEqual(r.status_code, HTTPStatus.OK)
                self.assertInLog("Failed to retrieve Model Name for Feedback.", log)

                segment_events = self.extractSegmentEventsFromLog(log)
                self.assertTrue(len(segment_events) > 0)
                for event in segment_events:
                    properties = event["properties"]
                    self.assertTrue("modelName" in properties)
                    self.assertEqual("", properties["modelName"])

    def test_feedback_segment_inline_suggestion_feedback_error(self):
        payload = {
            "inlineSuggestion": {
                "userActionTime": 3500,
                "documentUri": "file:///home/rbobbitt/ansible.yaml",
                "action": "3",  # invalid choice for action
                "suggestionId": str(uuid.uuid4()),
            }
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(self.api_version_reverse("feedback"), payload, format="json")
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            self.assert_error_detail(r, FeedbackValidationException.default_code)

            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertTrue(len(segment_events) > 0)
            for event in segment_events:
                self.assertTrue("inlineSuggestionFeedback", event["event"])
                properties = event["properties"]
                self.assertTrue("data" in properties)
                self.assertTrue("exception" in properties)
                self.assertEqual(
                    "file:///home/ano-user/ansible.yaml",
                    properties["data"]["inlineSuggestion"]["documentUri"],
                )
                self.assertIsNotNone(event["timestamp"])

    # Verify that sending an invalid ansibleContent feedback returns 200 as this
    # type of feedback is no longer supported and no parameter check is done.
    def test_feedback_segment_ansible_content_feedback(self):
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
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(self.api_version_reverse("feedback"), payload, format="json")
            self.assertEqual(r.status_code, HTTPStatus.OK)
            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertTrue(len(segment_events) == 0)

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
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(self.api_version_reverse("feedback"), payload, format="json")
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            self.assert_error_detail(r, FeedbackValidationException.default_code)

            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertTrue(len(segment_events) > 0)
            for event in segment_events:
                self.assertTrue("suggestionQualityFeedback", event["event"])
                properties = event["properties"]
                self.assertTrue("data" in properties)
                self.assertTrue("exception" in properties)
                self.assertEqual(
                    "Package name is changed",
                    properties["data"]["suggestionQualityFeedback"]["additionalComment"],
                )
                self.assertIsNotNone(event["timestamp"])

    def test_feedback_segment_sentiment_feedback_error(self):
        payload = {
            "sentimentFeedback": {
                # missing required key "value"
                "feedback": "This is a test feedback",
            }
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(self.api_version_reverse("feedback"), payload, format="json")
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            self.assert_error_detail(r, FeedbackValidationException.default_code)

            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertTrue(len(segment_events) > 0)
            for event in segment_events:
                self.assertTrue("suggestionQualityFeedback", event["event"])
                properties = event["properties"]
                self.assertTrue("data" in properties)
                self.assertTrue("exception" in properties)
                self.assertEqual(
                    "This is a test feedback",
                    properties["data"]["sentimentFeedback"]["feedback"],
                )
                self.assertIsNotNone(event["timestamp"])

    def test_feedback_segment_issue_feedback_error(self):
        payload = {
            "issueFeedback": {
                "type": "bug-report",
                # missing required key "title"
                "description": "This is a test description",
            }
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(self.api_version_reverse("feedback"), payload, format="json")
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            self.assert_error_detail(r, FeedbackValidationException.default_code)

            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertTrue(len(segment_events) > 0)
            for event in segment_events:
                self.assertTrue("issueFeedback", event["event"])
                properties = event["properties"]
                self.assertTrue("data" in properties)
                self.assertTrue("exception" in properties)
                self.assertEqual(
                    "This is a test description",
                    properties["data"]["issueFeedback"]["description"],
                )
                self.assertIsNotNone(event["timestamp"])

    def test_feedback_explanation(self):
        payload = {
            "playbookExplanationFeedback": {
                "action": 1,
                "explanationId": "2832e159-e0fe-4efc-9288-d60c96c88666",
            },
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(self.api_version_reverse("feedback"), payload, format="json")
            self.assertEqual(r.status_code, HTTPStatus.OK)

            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertTrue(len(segment_events) > 0)
            properties = segment_events[0]["properties"]
            self.assertEqual(properties["action"], "1")

    def test_feedback_generation(self):
        action = {
            "action": 3,
            "generationId": "2832e159-e0fe-4efc-9288-d60c96c88666",
            "wizardId": "f3c5a9c4-9170-40b3-b46f-de387234410b",
            "fromPage": 2,
            "toPage": 3,
        }
        payload = {
            "playbookGenerationAction": action,
            "roleGenerationAction": action,
        }
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(self.api_version_reverse("feedback"), payload, format="json")
            self.assertEqual(r.status_code, HTTPStatus.OK)

            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertTrue(len(segment_events) == 2)
            properties = segment_events[0]["properties"]
            self.assertEqual(properties["action"], 3)
            self.assertEqual(segment_events[0]["event"], "playbookGenerationAction")
            properties = segment_events[1]["properties"]
            self.assertEqual(properties["action"], 3)
            self.assertEqual(segment_events[1]["event"], "roleGenerationAction")

    def test_feedback_chatbot(self):
        payload = {
            "chatFeedback": {
                "query": "Hello chatbot",
                "response": {
                    "response": "Hello to you",
                    "conversation_id": TestFeedbackView.VALID_PAYLOAD_WITH_CONVERSATION_ID[
                        "conversation_id"
                    ],
                    "truncated": False,
                    "referenced_documents": [],
                },
                "sentiment": "1",
            }
        }
        self.user.rh_user_has_seat = True
        self.user.organization = ExternalOrganization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(self.api_version_reverse("feedback"), payload, format="json")
            self.assertEqual(r.status_code, HTTPStatus.OK)

            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertTrue(len(segment_events) > 0)
            self.assertEqual(
                segment_events[0]["properties"]["rh_user_org_id"],
                self.user.organization.id,
            )
            self.assertEqual(
                segment_events[0]["properties"]["chat_truncated"],
                False,
            )
            self.assertEqual(
                segment_events[0]["properties"]["chat_referenced_documents"],
                [],
            )
            self.assertEqual(
                segment_events[0]["properties"]["conversation_id"],
                TestFeedbackView.VALID_PAYLOAD_WITH_CONVERSATION_ID["conversation_id"],
            )
            self.assertEqual(
                segment_events[0]["properties"]["sentiment"],
                1,
            )
