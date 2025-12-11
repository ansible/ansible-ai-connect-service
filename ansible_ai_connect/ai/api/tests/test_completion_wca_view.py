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
import uuid
from http import HTTPStatus
from unittest.mock import Mock, patch

from django.apps import apps
from django.test import override_settings
from requests.exceptions import ReadTimeout

from ansible_ai_connect.ai.api.exceptions import (
    ModelTimeoutException,
    WcaCloudflareRejectionException,
    WcaEmptyResponseException,
    WcaHAPFilterRejectionException,
    WcaInferenceFailureException,
    WcaInstanceDeletedException,
    WcaInvalidModelIdException,
    WcaKeyNotFoundException,
    WcaModelIdNotFoundException,
    WcaNoDefaultModelIdException,
    WcaRequestIdCorrelationFailureException,
    WcaUserTrialExpiredException,
    WcaValidationFailureException,
)
from ansible_ai_connect.ai.api.model_pipelines.exceptions import (
    WcaKeyNotFound,
    WcaModelIdNotFound,
    WcaNoDefaultModelId,
    WcaUserTrialExpired,
)
from ansible_ai_connect.ai.api.model_pipelines.tests import mock_pipeline_config
from ansible_ai_connect.ai.api.model_pipelines.tests.test_wca_client import (
    WCA_REQUEST_ID_HEADER,
    MockResponse,
)
from ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_saas import (
    WCASaaSCompletionsPipeline,
)
from ansible_ai_connect.organizations.models import Organization
from ansible_ai_connect.test_utils import (
    APIVersionTestCaseBase,
    WisdomAppsBackendMocking,
    WisdomServiceAPITestCaseBase,
)

logger = logging.getLogger(__name__)

DEFAULT_SUGGESTION_ID = uuid.uuid4()


@override_settings(WCA_SECRET_BACKEND_TYPE="dummy")
class TestCompletionWCAView(
    APIVersionTestCaseBase, WisdomAppsBackendMocking, WisdomServiceAPITestCaseBase
):
    def stub_wca_client(
        self,
        status_code=None,
        mock_api_key=Mock(return_value="org-api-key"),
        mock_model_id=Mock(return_value="org-model-id"),
        response_data: dict = {
            "predictions": ["      ansible.builtin.apt:\n        name: apache2"]
        },
    ):
        model_input = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(DEFAULT_SUGGESTION_ID),
        }
        response = MockResponse(
            json=response_data,
            status_code=status_code,
            headers={WCA_REQUEST_ID_HEADER: str(DEFAULT_SUGGESTION_ID)},
        )
        model_client = WCASaaSCompletionsPipeline(mock_pipeline_config("wca"))
        model_client.session.post = Mock(return_value=response)
        model_client.get_api_key = mock_api_key
        model_client.get_model_id = mock_model_id
        model_client.get_token = Mock(return_value={"access_token": "abc"})
        return model_client, model_input

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1:valid")
    def test_wca_completion(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)

        stub = self.stub_wca_client(
            200,
        )
        model_client, model_input = stub
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
            r = self.client.post(self.api_version_reverse("completions"), model_input)
            self.assertEqual(r.status_code, HTTPStatus.OK)
            model_client.get_token.assert_called_once()
            self.assertEqual(
                model_client.session.post.call_args.args[0],
                "http://localhost/v1/wca/codegen/ansible",
            )
            self.assertEqual(
                model_client.session.post.call_args.kwargs["json"]["model_id"], "org-model-id"
            )

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1:valid")
    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_wca_completion_seated_user_missing_api_key(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)

        stub = self.stub_wca_client(
            200,
            Mock(side_effect=WcaKeyNotFound),
        )
        model_client, model_input = stub
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(self.api_version_reverse("completions"), model_input)
                self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
                self.assert_error_detail(
                    r, WcaKeyNotFoundException.default_code, WcaKeyNotFoundException.default_detail
                )
                self.assertInLog("A WCA Api Key was expected but not found", log)
                segment_events = self.extractSegmentEventsFromLog(log)
                self.assertTrue(len(segment_events) > 0)
                for event in segment_events:
                    properties = event["properties"]
                    self.assertEqual(properties["modelName"], "")
                    if event["event"] == "completion":
                        self.assertEqual(properties["response"]["status_code"], 403)
                    elif event["event"] == "prediction":
                        self.assertEqual(properties["problem"], "WcaKeyNotFound")

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1:valid")
    def test_wca_completion_user_not_linked_to_org(self):
        self.user.rh_user_has_seat = True
        self.user.organization = None
        self.client.force_authenticate(user=self.user)

        stub = self.stub_wca_client(
            200,
            mock_model_id=Mock(side_effect=WcaNoDefaultModelId),
        )
        model_client, model_input = stub
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(self.api_version_reverse("completions"), model_input)
                self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
                self.assert_error_detail(
                    r,
                    WcaNoDefaultModelIdException.default_code,
                    WcaNoDefaultModelIdException.default_detail,
                )
                self.assertInLog("No default WCA Model ID was found for suggestion", log)

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1:valid")
    def test_wca_completion_seated_user_missing_model_id(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)

        stub = self.stub_wca_client(
            200,
            mock_model_id=Mock(side_effect=WcaModelIdNotFound),
        )
        model_client, model_input = stub
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(self.api_version_reverse("completions"), model_input)
                self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
                self.assert_error_detail(
                    r,
                    WcaModelIdNotFoundException.default_code,
                    WcaModelIdNotFoundException.default_detail,
                )
                self.assertInLog("A WCA Model ID was expected but not found", log)

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1:valid")
    def test_wca_completion_seated_user_garbage_model_id(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)

        stub = self.stub_wca_client(
            400,
            mock_model_id=Mock(return_value="garbage"),
            response_data={"error": "Bad request: [('value_error', ('body', 'model_id'))]"},
        )
        model_client, model_input = stub
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(self.api_version_reverse("completions"), model_input)
                self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
                self.assert_error_detail(
                    r,
                    WcaInvalidModelIdException.default_code,
                    WcaInvalidModelIdException.default_detail,
                )
                self.assertInLog("WCA Model ID is invalid", log)

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1:valid")
    def test_wca_completion_seated_user_not_quite_valid_model_id(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)

        stub = self.stub_wca_client(
            400,
            mock_model_id=Mock(
                return_value="\\b8a86397-ef64-4ddb-bbf4-a2fd164577bb<|sepofid|>granite-3b"
            ),
            response_data={
                "detail": "Failed to parse space ID and model ID: Input should be a valid UUID,"
                " invalid character: expected an optional prefix of `urn:uuid:`"
                " followed by [0-9a-fA-F-], found `\\` at 1"
            },
        )
        model_client, model_input = stub
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(self.api_version_reverse("completions"), model_input)
                self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
                self.assert_error_detail(
                    r,
                    WcaInvalidModelIdException.default_code,
                    WcaInvalidModelIdException.default_detail,
                )
                self.assertInLog("WCA Model ID is invalid", log)

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1:valid")
    def test_wca_completion_seated_user_invalid_model_id_for_api_key(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)

        stub = self.stub_wca_client(
            403,
        )
        model_client, model_input = stub
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(self.api_version_reverse("completions"), model_input)
                self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
                self.assert_error_detail(
                    r,
                    WcaInvalidModelIdException.default_code,
                    WcaInvalidModelIdException.default_detail,
                )
                self.assertInLog("WCA Model ID is invalid", log)

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1:valid")
    def test_wca_completion_seated_user_empty_response(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)

        stub = self.stub_wca_client(
            204,
        )
        model_client, model_input = stub
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(self.api_version_reverse("completions"), model_input)
                self.assertEqual(r.status_code, HTTPStatus.NO_CONTENT)
                self.assert_error_detail(
                    r,
                    WcaEmptyResponseException.default_code,
                    WcaEmptyResponseException.default_detail,
                )
                self.assertInLog("WCA returned an empty response", log)

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1:valid")
    def test_wca_completion_seated_user_cloudflare_rejection(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)

        model_client, model_input = self.stub_wca_client()
        response = MockResponse(
            json=[],
            text="cloudflare rejection",
            status_code=HTTPStatus.FORBIDDEN,
        )
        model_client.session.post = Mock(return_value=response)
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(self.api_version_reverse("completions"), model_input)
                self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
                self.assert_error_detail(
                    r,
                    WcaCloudflareRejectionException.default_code,
                    WcaCloudflareRejectionException.default_detail,
                )
                self.assertInLog("Cloudflare rejected the request", log)

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1:valid")
    def test_wca_completion_seated_user_hap_filter_rejection(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)

        model_client, model_input = self.stub_wca_client()
        response = MockResponse(
            json={"detail": "our filters detected a potential problem with entities in your input"},
            status_code=HTTPStatus.BAD_REQUEST,
        )
        model_client.session.post = Mock(return_value=response)
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(self.api_version_reverse("completions"), model_input)
                self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
                self.assert_error_detail(
                    r,
                    WcaHAPFilterRejectionException.default_code,
                    WcaHAPFilterRejectionException.default_detail,
                )
                self.assertInLog("WCA Hate, Abuse, and Profanity filter rejected the request", log)

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1:valid")
    def test_wca_completion_wml_api_call_failed(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)

        model_client, model_input = self.stub_wca_client()
        response = MockResponse(
            json={"detail": "WML API call failed: Deployment id or name banana was not found."},
            status_code=HTTPStatus.NOT_FOUND,
            headers={"Content-Type": "application/json"},
        )
        model_client.session.post = Mock(return_value=response)
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(self.api_version_reverse("completions"), model_input)
                self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
                self.assert_error_detail(
                    r,
                    WcaInvalidModelIdException.default_code,
                    WcaInvalidModelIdException.default_detail,
                )
                self.assertInLog("WCA Model ID is invalid", log)

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1:valid")
    def test_wca_completion_seated_user_trial_expired_rejection(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)

        model_client, model_input = self.stub_wca_client()
        model_client.session.post = Mock(side_effect=WcaUserTrialExpired())
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(self.api_version_reverse("completions"), model_input)
                self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
                self.assert_error_detail(
                    r,
                    WcaUserTrialExpiredException.default_code,
                    WcaUserTrialExpiredException.default_detail,
                )
                self.assertInLog("User trial expired", log)

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1:valid")
    def test_wca_completion_seated_user_trial_expired(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)

        stub = self.stub_wca_client(
            403, response_data={"message_id": "WCA-0001-E", "detail": "The CUH limit is reached."}
        )
        model_client, model_input = stub
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(self.api_version_reverse("completions"), model_input)
                self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
                self.assert_error_detail(
                    r,
                    WcaUserTrialExpiredException.default_code,
                    WcaUserTrialExpiredException.default_detail,
                )
                self.assertInLog("User trial expired", log)

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1:valid")
    def test_wca_completion_seated_user_model_id_error(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)

        model_client, model_input = self.stub_wca_client()
        response = MockResponse(
            json={"error": "Bad request: [('value_error', ('body', 'model_id'))]"},
            status_code=HTTPStatus.BAD_REQUEST,
        )
        model_client.session.post = Mock(return_value=response)
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(self.api_version_reverse("completions"), model_input)
                self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
                self.assert_error_detail(
                    r,
                    WcaInvalidModelIdException.default_code,
                    WcaInvalidModelIdException.default_detail,
                )
                self.assertInLog("WCA Model ID is invalid", log)

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1:valid<|sepofid|>valid")
    def test_wca_completion_timeout_single_task(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)

        stub = self.stub_wca_client(
            200,
        )
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(DEFAULT_SUGGESTION_ID),
        }
        model_client, _ = stub
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
            r = self.client.post(self.api_version_reverse("completions"), payload)
            self.assertEqual(r.status_code, HTTPStatus.OK)
            self.assertEqual(model_client.session.post.call_args[1]["timeout"], 1000)

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1:valid<|sepofid|>valid")
    def test_wca_completion_timeout_multi_task(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)

        stub = self.stub_wca_client(
            200,
            response_data={
                "predictions": [
                    "- name:  Install Apache\n  ansible.builtin.package:\n    name: apache2\n    "  # noqa: E501
                    "state: present\n- name:  start Apache\n  ansible.builtin.service:\n    name: apache2\n"  # noqa: E501
                    "    state: started\n    enabled: true\n"
                ],
            },
        )
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  "
            "tasks:\n    # Install Apache & start Apache\n",
            "suggestionId": str(DEFAULT_SUGGESTION_ID),
        }
        model_client, _ = stub
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
            r = self.client.post(self.api_version_reverse("completions"), payload)
            self.assertEqual(r.status_code, HTTPStatus.OK)
            self.assertEqual(model_client.session.post.call_args[1]["timeout"], 2000)

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1:valid<|sepofid|>valid")
    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_wca_completion_timed_out(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)

        stub = self.stub_wca_client(
            200,
        )
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  "
            "tasks:\n    # Install Apache & start Apache\n",
            "suggestionId": str(DEFAULT_SUGGESTION_ID),
        }
        model_client, _ = stub
        model_client.session.post = Mock(side_effect=ReadTimeout())
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(self.api_version_reverse("completions"), payload)
                self.assertEqual(r.status_code, HTTPStatus.NO_CONTENT)
                self.assert_error_detail(
                    r,
                    ModelTimeoutException.default_code,
                    ModelTimeoutException.default_detail,
                )
                segment_events = self.extractSegmentEventsFromLog(log)
                self.assertTrue(len(segment_events) > 0)
                for event in segment_events:
                    if event["event"] == "prediction":
                        properties = event["properties"]
                        self.assertTrue(properties["exception"])
                        self.assertEqual(properties["problem"], "ModelTimeoutError")

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1:valid")
    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_wca_completion_request_id_correlation_failure(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)

        stub = self.stub_wca_client(
            200,
        )
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  "
            "tasks:\n    # Install Apache & start Apache\n",
            "suggestionId": str(DEFAULT_SUGGESTION_ID),
        }
        x_request_id = uuid.uuid4()
        response = MockResponse(
            json={},
            status_code=200,
            headers={WCA_REQUEST_ID_HEADER: str(x_request_id)},
        )

        model_client, _ = stub
        model_client.session.post = Mock(return_value=response)
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(self.api_version_reverse("completions"), payload)
                self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
                self.assert_error_detail(
                    r,
                    WcaRequestIdCorrelationFailureException.default_code,
                    WcaRequestIdCorrelationFailureException.default_detail,
                )
                segment_events = self.extractSegmentEventsFromLog(log)
                self.assertTrue(len(segment_events) > 0)
                for event in segment_events:
                    if event["event"] == "prediction":
                        properties = event["properties"]
                        self.assertTrue(properties["exception"])
                        self.assertEqual(properties["problem"], "WcaRequestIdCorrelationFailure")
                self.assertInLog(f"suggestion_id: '{DEFAULT_SUGGESTION_ID}'", log)
                self.assertInLog(f"x_request_id: '{x_request_id}'", log)

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1:valid")
    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    @patch("ansible_ai_connect.main.middleware.send_segment_event")
    def test_wca_completion_segment_event_with_invalid_model_id_error(
        self, mock_send_segment_event
    ):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)

        stub = self.stub_wca_client(
            400,
            mock_model_id=Mock(return_value="garbage"),
            response_data={"error": "Bad request: [('value_error', ('body', 'model_id'))]"},
        )
        model_client, model_input = stub
        model_input["prompt"] = (
            "---\n- hosts: all\n  become: yes\n\n  tasks:\n    # Install Apache & start apache\n"
        )
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(self.api_version_reverse("completions"), model_input)
                self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
                self.assert_error_detail(
                    r,
                    WcaInvalidModelIdException.default_code,
                    WcaInvalidModelIdException.default_detail,
                )
                self.assertInLog("WCA Model ID is invalid", log)

                actual_event = mock_send_segment_event.call_args_list[0][0][0]
                self.assertEqual(actual_event.get("promptType"), "MULTITASK")

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1:valid")
    def test_wca_completion_wca_instance_deleted(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)

        model_client, model_input = self.stub_wca_client()
        response = MockResponse(
            json={
                "detail": (
                    "Failed to get remaining capacity from Metering API: "
                    "The WCA instance 'banana' has been deleted."
                )
            },
            status_code=HTTPStatus.NOT_FOUND,
        )
        model_client.session.post = Mock(return_value=response)
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(self.api_version_reverse("completions"), model_input)
                self.assertEqual(r.status_code, HTTPStatus.IM_A_TEAPOT)
                self.assert_error_detail(
                    r,
                    WcaInstanceDeletedException.default_code,
                    WcaInstanceDeletedException.default_detail,
                )
                self.assertInLog("WCA Instance has been deleted", log)

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1:valid")
    def test_wca_inference_failed(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)

        model_client, model_input = self.stub_wca_client()
        response = MockResponse(
            json={},
            status_code=HTTPStatus.NOT_FOUND,
            headers={"Content-Type": "application/json"},
        )
        model_client.session.post = Mock(return_value=response)
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(self.api_version_reverse("completions"), model_input)
                self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
                self.assert_error_detail(
                    r,
                    WcaInferenceFailureException.default_code,
                    WcaInferenceFailureException.default_detail,
                )
                self.assertInLog("WCA inference failed", log)

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1:valid")
    def test_wca_validation_failed(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)

        model_client, model_input = self.stub_wca_client()
        response = MockResponse(
            json={"detail": "Validation failed."},
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            headers={"Content-Type": "application/json"},
        )
        model_client.session.post = Mock(return_value=response)
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=model_client),
        ):
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(self.api_version_reverse("completions"), model_input)
                self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
                self.assert_error_detail(
                    r,
                    WcaValidationFailureException.default_code,
                    WcaValidationFailureException.default_detail,
                )
                self.assertInLog("WCA failed to validate response from model", log)
