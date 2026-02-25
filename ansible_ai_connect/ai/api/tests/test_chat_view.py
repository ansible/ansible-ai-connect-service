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
import json
import logging
import random
import string
from http import HTTPStatus
from unittest import mock, skip
from unittest.mock import Mock, patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.http import StreamingHttpResponse
from django.test import override_settings

from ansible_ai_connect.ai.api.exceptions import (
    ChatbotForbiddenException,
    ChatbotInternalServerException,
    ChatbotInvalidResponseException,
    ChatbotNotEnabledException,
    ChatbotPromptTooLongException,
    ChatbotUnauthorizedException,
    ChatbotValidationException,
)
from ansible_ai_connect.ai.api.model_pipelines.http.pipelines import (
    HttpChatBotPipeline,
    HttpStreamingChatBotPipeline,
)
from ansible_ai_connect.ai.api.model_pipelines.tests import mock_pipeline_config
from ansible_ai_connect.main import ssl_manager
from ansible_ai_connect.organizations.models import Organization
from ansible_ai_connect.test_utils import (
    APIVersionTestCaseBase,
    WisdomServiceAPITestCaseBase,
)

logger = logging.getLogger(__name__)


class TestChatView(APIVersionTestCaseBase, WisdomServiceAPITestCaseBase):

    VALID_PAYLOAD = {
        "query": "Hello",
    }

    VALID_PAYLOAD_WITH_CONVERSATION_ID = {
        "query": "Hello",
        "conversation_id": "ABC-123e4567-e89b-12d3-a456-426614174000",  # Non-UUIDs are fine here.
    }

    INVALID_PAYLOAD = {
        "conversation_id": "123e4567-e89b-12d3-a456-426614174000",
    }

    PAYLOAD_INVALID_RESPONSE = {
        "query": "Return an invalid response",
    }

    PAYLOAD_UNAUTHORIZERD = {
        "query": "Return the unauthorized status code",
    }

    PAYLOAD_FORBIDDEN = {
        "query": "Return the forbidden status code",
    }

    PAYLOAD_PROMPT_TOO_LONG = {
        "query": "Return the prompt too long status code",
    }

    PAYLOAD_PROMPT_VALIDATION_FAILED = {
        "query": "Return the validation failed status code",
    }

    PAYLOAD_INTERNAL_SERVER_ERROR = {
        "query": "Return the internal server error status code",
    }

    PAYLOAD_WITH_MODEL_AND_PROVIDER = {
        "query": "Payload with a non-default model and a non-default provider",
        "model": "non_default_model",
        "provider": "non_default_provider",
    }

    PAYLOAD_WITH_SYSTEM_PROMPT_OVERRIDE = {
        "query": "Payload with a system prompt override",
        "system_prompt": "System prompt override",
    }

    PAYLOAD_WITH_NO_TOOLS_OPTION = {
        "query": "Payload with no tools option",
        "no_tools": True,
    }

    JSON_RESPONSE = {
        "response": "AAP 2.5 introduces an updated, unified UI.",
        "conversation_id": "123e4567-e89b-12d3-a456-426614174000",
        "truncated": False,
        "referenced_documents": [],
    }

    def setUp(self):
        super().setUp()
        (org, _) = Organization.objects.get_or_create(id=123, telemetry_opt_out=False)
        self.user.organization = org
        self.user.rh_internal = True

        self.ssl_patcher = mock.patch.object(ssl_manager.ssl_manager, "get_requests_session")
        self.mock_session_factory = self.ssl_patcher.start()

        # Create mock session that will be used by all pipelines
        self.mock_session = mock.Mock()
        self.mock_session.post.side_effect = TestChatView.mocked_requests_post
        self.mock_session_factory.return_value = self.mock_session

    def tearDown(self):
        super().tearDown()
        self.ssl_patcher.stop()

    @staticmethod
    def mocked_requests_post(*args, **kwargs):
        class MockResponse:
            def __init__(self, json_data, status_code):
                self.json_data = json_data
                self.status_code = status_code
                self.text = json.dumps(json_data)

            def json(self):
                return self.json_data

        # Make sure that the given json data is serializable
        input = json.dumps(kwargs["json"])

        json_response = {
            "response": "AAP 2.5 introduces an updated, unified UI.",
            "conversation_id": "123e4567-e89b-12d3-a456-426614174000",
            "truncated": False,
            "referenced_documents": [],
        }
        status_code = 200

        if kwargs["json"]["query"] == TestChatView.PAYLOAD_INVALID_RESPONSE["query"]:
            json_response = {
                "response": "AAP 2.5 introduces an updated, unified UI.",
                # "conversation_id": "123e4567-e89b-12d3-a456-426614174000",
                "truncated": False,
                "referenced_documents": [],
            }
        elif kwargs["json"]["query"] == TestChatView.PAYLOAD_UNAUTHORIZERD["query"]:
            status_code = 401
            json_response = {
                "detail": "Unauthorized",
            }
        elif kwargs["json"]["query"] == TestChatView.PAYLOAD_FORBIDDEN["query"]:
            status_code = 403
            json_response = {
                "detail": "Forbidden",
            }
        elif kwargs["json"]["query"] == TestChatView.PAYLOAD_PROMPT_TOO_LONG["query"]:
            status_code = 413
            json_response = {
                "detail": "Prompt too long",
            }
        elif kwargs["json"]["query"] == TestChatView.PAYLOAD_PROMPT_VALIDATION_FAILED["query"]:
            status_code = 422
            json_response = {
                "detail": "Validation failed",
            }
        elif kwargs["json"]["query"] == TestChatView.PAYLOAD_INTERNAL_SERVER_ERROR["query"]:
            status_code = 500
            json_response = {
                "detail": "Internal server error",
            }
        elif (
            kwargs["json"]["query"] == TestChatView.PAYLOAD_WITH_MODEL_AND_PROVIDER["query"]
            or kwargs["json"]["query"] == TestChatView.PAYLOAD_WITH_SYSTEM_PROMPT_OVERRIDE["query"]
            or kwargs["json"]["query"] == TestChatView.PAYLOAD_WITH_NO_TOOLS_OPTION["query"]
        ):
            status_code = 200
            json_response["response"] = input
        return MockResponse(json_response, status_code)

    @override_settings(CHATBOT_DEFAULT_PROVIDER="wisdom")
    def query_with_no_error(self, payload):
        # SSL manager mocking is now handled globally in setUp()
        return self.client.post(self.api_version_reverse("chat"), payload, format="json")

    @override_settings(CHATBOT_DEFAULT_PROVIDER="")
    def query_without_chat_config(self, payload):
        # SSL manager mocking is now handled globally in setUp()
        return self.client.post(self.api_version_reverse("chat"), payload, format="json")

    def assert_test(
        self,
        payload,
        expected_status_code=200,
        expected_exception=None,
        expected_log_message=None,
        user=None,
    ):
        if user is None:
            user = self.user
        with (
            patch.object(
                apps.get_app_config("ai"),
                "get_model_pipeline",
                Mock(return_value=HttpChatBotPipeline(mock_pipeline_config("http"))),
            ),
            self.assertLogs(logger="root", level="DEBUG") as log,
        ):
            self.client.force_authenticate(user=user)

            if expected_exception == ChatbotNotEnabledException:
                r = self.query_without_chat_config(payload)
            else:
                r = self.query_with_no_error(payload)

            self.assertEqual(r.status_code, expected_status_code)
            if expected_exception is not None:
                self.assert_error_detail(
                    r, expected_exception().default_code, expected_exception().default_detail
                )
                self.assertInLog(expected_log_message, log)
        return r

    def test_chat(self):
        self.assert_test(TestChatView.VALID_PAYLOAD)

    def test_chat_with_conversation_id(self):
        self.assert_test(TestChatView.VALID_PAYLOAD_WITH_CONVERSATION_ID)

    def test_chat_not_enabled_exception(self):
        self.assert_test(
            TestChatView.VALID_PAYLOAD, 503, ChatbotNotEnabledException, "Chatbot is not enabled"
        )

    def test_chat_invalid_response_exception(self):
        self.assert_test(
            TestChatView.PAYLOAD_INVALID_RESPONSE,
            500,
            ChatbotInvalidResponseException,
            "ChatbotInvalidResponseException",
        )

    def test_chat_unauthorized_exception(self):
        self.assert_test(
            TestChatView.PAYLOAD_UNAUTHORIZERD,
            503,
            ChatbotUnauthorizedException,
            "ChatbotUnauthorizedException",
        )

    def test_chat_forbidden_exception(self):
        self.assert_test(
            TestChatView.PAYLOAD_FORBIDDEN,
            403,
            ChatbotForbiddenException,
            "ChatbotForbiddenException",
        )

    def test_chat_prompt_too_long_exception(self):
        self.assert_test(
            TestChatView.PAYLOAD_PROMPT_TOO_LONG,
            413,
            ChatbotPromptTooLongException,
            "ChatbotPromptTooLongException",
        )

    def test_chat_validation_exception(self):
        self.assert_test(
            TestChatView.PAYLOAD_PROMPT_VALIDATION_FAILED,
            422,
            ChatbotValidationException,
            "ChatbotValidationException",
        )

    def test_chat_internal_server_exception(self):
        self.assert_test(
            TestChatView.PAYLOAD_INTERNAL_SERVER_ERROR,
            500,
            ChatbotInternalServerException,
            "ChatbotInternalServerException",
        )

    def test_chat_with_model_and_provider(self):
        r = self.assert_test(TestChatView.PAYLOAD_WITH_MODEL_AND_PROVIDER)
        self.assertIn('"model": "non_default_model"', r.data["response"])
        self.assertIn('"provider": "non_default_provider"', r.data["response"])

    def test_chat_with_system_prompt_override(self):
        r = self.assert_test(TestChatView.PAYLOAD_WITH_SYSTEM_PROMPT_OVERRIDE)
        self.assertIn(TestChatView.PAYLOAD_WITH_SYSTEM_PROMPT_OVERRIDE["query"], r.data["response"])

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_operational_telemetry(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)
        with (
            patch.object(
                apps.get_app_config("ai"),
                "get_model_pipeline",
                Mock(
                    return_value=HttpChatBotPipeline(
                        mock_pipeline_config("http", model_id="granite-8b")
                    )
                ),
            ),
            self.assertLogs(logger="root", level="DEBUG") as log,
        ):
            r = self.query_with_no_error(TestChatView.VALID_PAYLOAD_WITH_CONVERSATION_ID)
            self.assertEqual(r.status_code, HTTPStatus.OK)
            segment_events = self.extractSegmentEventsFromLog(log)
            # Verify that chat_prompt is not found
            self.assertNotIn("chat_prompt", segment_events[0]["properties"])
            self.assertEqual(
                segment_events[0]["properties"]["conversation_id"],
                TestChatView.VALID_PAYLOAD_WITH_CONVERSATION_ID["conversation_id"],
            )
            self.assertEqual(segment_events[0]["properties"]["modelName"], "granite-8b")
            # Verify that chat_response is not found
            self.assertNotIn("chat_response", segment_events[0]["properties"])
            self.assertEqual(
                segment_events[0]["properties"]["chat_truncated"],
                TestChatView.JSON_RESPONSE["truncated"],
            )
            self.assertEqual(len(segment_events[0]["properties"]["chat_referenced_documents"]), 0)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_operational_telemetry_error(self):
        self.client.force_authenticate(user=self.user)
        with (
            patch.object(
                apps.get_app_config("ai"),
                "get_model_pipeline",
                Mock(return_value=HttpChatBotPipeline(mock_pipeline_config("http"))),
            ),
            self.assertLogs(logger="root", level="DEBUG") as log,
        ):
            r = self.query_with_no_error(TestChatView.PAYLOAD_INVALID_RESPONSE)
            self.assertEqual(r.status_code, 500)
            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertEqual(
                segment_events[0]["properties"]["rh_user_org_id"],
                123,
            )
            self.assertEqual(
                segment_events[0]["properties"]["problem"],
                "Invalid response",
            )

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_operational_telemetry_limit_exceeded(self):
        q = "".join("hello " for i in range(6500))
        payload = {
            "query": q,
        }
        self.client.force_authenticate(user=self.user)
        with (
            patch.object(
                apps.get_app_config("ai"),
                "get_model_pipeline",
                Mock(return_value=HttpChatBotPipeline(mock_pipeline_config("http"))),
            ),
            self.assertLogs(logger="root", level="DEBUG") as log,
        ):
            r = self.query_with_no_error(payload)
            self.assertEqual(r.status_code, 200)
            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertEqual(
                segment_events[0]["properties"]["rh_user_org_id"],
                123,
            )
            # Verify that chat_response is not found
            self.assertNotIn("chat_response", segment_events[0]["properties"])

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_operational_telemetry_anonymizer(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)
        with (
            patch.object(
                apps.get_app_config("ai"),
                "get_model_pipeline",
                Mock(return_value=HttpChatBotPipeline(mock_pipeline_config("http"))),
            ),
            self.assertLogs(logger="root", level="DEBUG") as log,
        ):
            r = self.query_with_no_error(
                {
                    "query": "Hello ansible@ansible.com",
                    "conversation_id": "123e4567-e89b-12d3-a456-426614174000",
                }
            )
            self.assertEqual(r.status_code, HTTPStatus.OK)
            segment_events = self.extractSegmentEventsFromLog(log)
            # Verify that chat_prompt is not found
            self.assertNotIn("chat_prompt", segment_events[0]["properties"])

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_operational_telemetry_with_system_prompt_override(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)
        with (
            patch.object(
                apps.get_app_config("ai"),
                "get_model_pipeline",
                Mock(
                    return_value=HttpChatBotPipeline(
                        mock_pipeline_config("http", model_id="granite-8b")
                    )
                ),
            ),
            self.assertLogs(logger="root", level="DEBUG") as log,
        ):
            r = self.query_with_no_error(TestChatView.PAYLOAD_WITH_SYSTEM_PROMPT_OVERRIDE)
            self.assertEqual(r.status_code, HTTPStatus.OK)
            segment_events = self.extractSegmentEventsFromLog(log)
            # Verify that chat_prompt is not found
            self.assertNotIn("chat_prompt", segment_events[0]["properties"])
            self.assertEqual(segment_events[0]["properties"]["modelName"], "granite-8b")
            # Verify that chat_response is not found
            self.assertNotIn("chat_response", segment_events[0]["properties"])
            self.assertEqual(
                segment_events[0]["properties"]["chat_truncated"],
                TestChatView.JSON_RESPONSE["truncated"],
            )
            self.assertEqual(len(segment_events[0]["properties"]["chat_referenced_documents"]), 0)
            self.assertEqual(
                segment_events[0]["properties"]["chat_system_prompt"],
                TestChatView.PAYLOAD_WITH_SYSTEM_PROMPT_OVERRIDE["system_prompt"],
            )
            self.assertFalse(segment_events[0]["properties"]["no_tools"])

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_operational_telemetry_with_no_tools_option(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)
        with (
            patch.object(
                apps.get_app_config("ai"),
                "get_model_pipeline",
                Mock(
                    return_value=HttpChatBotPipeline(
                        mock_pipeline_config("http", model_id="granite-8b")
                    )
                ),
            ),
            self.assertLogs(logger="root", level="DEBUG") as log,
        ):
            r = self.query_with_no_error(TestChatView.PAYLOAD_WITH_NO_TOOLS_OPTION)
            self.assertEqual(r.status_code, HTTPStatus.OK)
            segment_events = self.extractSegmentEventsFromLog(log)
            # Verify that chat_prompt is not found
            self.assertNotIn("chat_prompt", segment_events[0]["properties"])
            self.assertEqual(segment_events[0]["properties"]["modelName"], "granite-8b")
            # Verify that chat_response is not found
            self.assertNotIn("chat_response", segment_events[0]["properties"])
            self.assertEqual(
                segment_events[0]["properties"]["chat_truncated"],
                TestChatView.JSON_RESPONSE["truncated"],
            )
            self.assertTrue(segment_events[0]["properties"]["no_tools"])

    def test_chat_rate_limit(self):
        # Call chat API five times using self.user
        for i in range(5):
            self.assert_test(TestChatView.VALID_PAYLOAD)
        try:
            username = "u" + "".join(random.choices(string.digits, k=5))
            password = "secret"
            email = "user2@example.com"
            self.user2 = get_user_model().objects.create_user(
                username=username,
                email=email,
                password=password,
            )
            (org, _) = Organization.objects.get_or_create(id=123, telemetry_opt_out=False)
            self.user2.organization = org
            self.user2.rh_internal = True
            # Call chart API five times using self.user2
            for i in range(5):
                self.assert_test(TestChatView.VALID_PAYLOAD, user=self.user2)
            # The next chat API call should be the 11th from two users and should receive a 429.
            self.assert_test(TestChatView.VALID_PAYLOAD, expected_status_code=429, user=self.user2)
        finally:
            if self.user2:
                self.user2.delete()

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_operational_telemetry_excludes_chat_prompt_by_default(self):
        """Test that chat_prompt is excluded from telemetry by default (via allow list)"""
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)
        with (
            patch.object(
                apps.get_app_config("ai"),
                "get_model_pipeline",
                Mock(
                    return_value=HttpChatBotPipeline(
                        mock_pipeline_config("http", model_id="granite-8b")
                    )
                ),
            ),
            self.assertLogs(logger="root", level="DEBUG") as log,
        ):
            r = self.query_with_no_error(TestChatView.VALID_PAYLOAD_WITH_CONVERSATION_ID)
            self.assertEqual(r.status_code, HTTPStatus.OK)
            segment_events = self.extractSegmentEventsFromLog(log)
            # Verify that chat_prompt is not found
            self.assertNotIn("chat_prompt", segment_events[0]["properties"])
            self.assertEqual(
                segment_events[0]["properties"]["conversation_id"],
                TestChatView.VALID_PAYLOAD_WITH_CONVERSATION_ID["conversation_id"],
            )
            self.assertEqual(segment_events[0]["properties"]["modelName"], "granite-8b")

    def test_not_rh_internal_user(self):
        try:
            username = "u" + "".join(random.choices(string.digits, k=5))
            self.user2 = get_user_model().objects.create_user(
                username=username,
            )
            self.user2.organization = Organization.objects.get_or_create(
                id=123, telemetry_opt_out=False
            )[0]
            self.user2.rh_internal = False
            self.assert_test(TestChatView.VALID_PAYLOAD, expected_status_code=403, user=self.user2)
        finally:
            if self.user2:
                self.user2.delete()


class TestStreamingChatView(APIVersionTestCaseBase, WisdomServiceAPITestCaseBase):
    api_version = "v1"

    def setUp(self):
        super().setUp()
        (org, _) = Organization.objects.get_or_create(id=123, telemetry_opt_out=False)
        self.user.organization = org
        self.user.rh_internal = True

    @staticmethod
    def mocked_response(*args, **kwargs):

        # Make sure that the given json data is serializable
        input = json.dumps(kwargs["json"])
        assert input is not None

        json_response = {
            "response": "AAP 2.5 introduces an updated, unified UI.",
            "conversation_id": "123e4567-e89b-12d3-a456-426614174000",
            "truncated": False,
            "referenced_documents": [],
        }
        status_code = 200

        if kwargs["json"]["query"] == TestChatView.PAYLOAD_INTERNAL_SERVER_ERROR["query"]:
            status_code = 500
            json_response = {
                "detail": "Internal server error",
            }

        response = StreamingHttpResponse(streaming_content=[json.dumps(json_response)])
        response.status_code = status_code
        return response

    @override_settings(CHATBOT_DEFAULT_PROVIDER="wisdom")
    @mock.patch(
        "ansible_ai_connect.ai.api.model_pipelines.http.pipelines."
        "HttpStreamingChatBotPipeline.get_streaming_http_response",
    )
    def query_with_status_code_override(self, payload, mock):
        mock.return_value = TestStreamingChatView.mocked_response(json=payload)
        return self.client.post(self.api_version_reverse("streaming_chat"), payload, format="json")

    @override_settings(CHATBOT_DEFAULT_PROVIDER="")
    def query_without_chat_config(self, payload):
        return self.client.post(self.api_version_reverse("streaming_chat"), payload, format="json")

    @override_settings(CHATBOT_DEFAULT_PROVIDER="wisdom")
    @mock.patch(
        "ansible_ai_connect.ai.api.model_pipelines.http.pipelines."
        "HttpStreamingChatBotPipeline.get_streaming_http_response",
    )
    def query_with_no_error(self, payload, mock):
        mock.return_value = TestStreamingChatView.mocked_response(json=payload)
        return self.client.post(self.api_version_reverse("streaming_chat"), payload, format="json")

    def assert_test(
        self,
        payload,
        expected_status_code=200,
        expected_exception=None,
        expected_log_message=None,
        user=None,
    ):
        if user is None:
            user = self.user
        with (
            patch.object(
                apps.get_app_config("ai"),
                "get_model_pipeline",
                Mock(return_value=HttpStreamingChatBotPipeline(mock_pipeline_config("http"))),
            ),
            self.assertLogs(logger="root", level="DEBUG") as log,
        ):
            self.client.force_authenticate(user=user)

            if expected_status_code >= 400:
                if expected_exception == ChatbotNotEnabledException:
                    r = self.query_without_chat_config(payload)
                else:
                    r = self.query_with_status_code_override(payload)
            else:
                r = self.query_with_no_error(payload)

            self.assertEqual(r.status_code, expected_status_code)
            if expected_exception is not None:
                self.assert_error_detail(
                    r, expected_exception().default_code, expected_exception().default_detail
                )
                self.assertInLog(expected_log_message, log)
        return r

    def test_chat(self):
        self.assert_test(TestChatView.VALID_PAYLOAD)

    def test_chat_with_conversation_id(self):
        self.assert_test(TestChatView.VALID_PAYLOAD_WITH_CONVERSATION_ID)

    def test_chat_not_enabled_exception(self):
        self.assert_test(
            TestChatView.VALID_PAYLOAD, 503, ChatbotNotEnabledException, "Chatbot is not enabled"
        )

    def test_chat_internal_server_exception(self):
        self.assert_test(
            TestChatView.PAYLOAD_INTERNAL_SERVER_ERROR,
            500,
            ChatbotInternalServerException,
            "ChatbotInternalServerException",
        )

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_operational_telemetry(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)
        with (
            patch.object(
                apps.get_app_config("ai"),
                "get_model_pipeline",
                Mock(
                    return_value=HttpStreamingChatBotPipeline(
                        mock_pipeline_config("http", model_id="granite-8b")
                    )
                ),
            ),
            self.assertLogs(logger="root", level="DEBUG") as log,
        ):
            r = self.query_with_no_error(TestChatView.VALID_PAYLOAD_WITH_CONVERSATION_ID)
            self.assertEqual(r.status_code, HTTPStatus.OK)
            segment_events = self.extractSegmentEventsFromLog(log)
            # Verify that chat_prompt is not found
            self.assertNotIn("chat_prompt", segment_events[0]["properties"])
            self.assertEqual(
                segment_events[0]["properties"]["conversation_id"],
                TestChatView.VALID_PAYLOAD_WITH_CONVERSATION_ID["conversation_id"],
            )
            self.assertEqual(segment_events[0]["properties"]["modelName"], "granite-8b")
            self.assertEqual(
                segment_events[0]["properties"]["chat_truncated"],
                TestChatView.JSON_RESPONSE["truncated"],
            )
            self.assertEqual(len(segment_events[0]["properties"]["chat_referenced_documents"]), 0)

    @skip("We no longer include prompt/response in telemetry events")
    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_operational_telemetry_limit_exceeded(self):
        q = "".join("hello " for i in range(6500))
        payload = {
            "query": q,
        }
        self.client.force_authenticate(user=self.user)
        with (
            patch.object(
                apps.get_app_config("ai"),
                "get_model_pipeline",
                Mock(return_value=HttpStreamingChatBotPipeline(mock_pipeline_config("http"))),
            ),
            self.assertLogs(logger="root", level="DEBUG") as log,
        ):
            r = self.query_with_no_error(payload)
            self.assertEqual(r.status_code, 200)
            segment_events = self.extractSegmentEventsFromLog(log)
            self.assertEqual(
                segment_events[0]["properties"]["rh_user_org_id"],
                123,
            )
            # Verify that chat_response is not found
            self.assertNotIn("chat_response", segment_events[0]["properties"])

    @skip("We no longer include prompt/response in telemetry events")
    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_operational_telemetry_anonymizer(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)
        with (
            patch.object(
                apps.get_app_config("ai"),
                "get_model_pipeline",
                Mock(return_value=HttpStreamingChatBotPipeline(mock_pipeline_config("http"))),
            ),
            self.assertLogs(logger="root", level="DEBUG") as log,
        ):
            r = self.query_with_no_error(
                {
                    "query": "Hello ansible@ansible.com",
                    "conversation_id": "123e4567-e89b-12d3-a456-426614174000",
                }
            )
            self.assertEqual(r.status_code, HTTPStatus.OK)
            segment_events = self.extractSegmentEventsFromLog(log)
            # Verify that chat_prompt is not found
            self.assertNotIn("chat_prompt", segment_events[0]["properties"])

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_operational_telemetry_with_system_prompt_override(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)
        with (
            patch.object(
                apps.get_app_config("ai"),
                "get_model_pipeline",
                Mock(
                    return_value=HttpStreamingChatBotPipeline(
                        mock_pipeline_config("http", model_id="granite-8b")
                    )
                ),
            ),
            self.assertLogs(logger="root", level="DEBUG") as log,
        ):
            r = self.query_with_no_error(TestChatView.PAYLOAD_WITH_SYSTEM_PROMPT_OVERRIDE)
            self.assertEqual(r.status_code, HTTPStatus.OK)
            segment_events = self.extractSegmentEventsFromLog(log)
            # Verify that chat_prompt is not found
            self.assertNotIn("chat_prompt", segment_events[0]["properties"])
            self.assertEqual(segment_events[0]["properties"]["modelName"], "granite-8b")
            self.assertEqual(
                segment_events[0]["properties"]["chat_truncated"],
                TestChatView.JSON_RESPONSE["truncated"],
            )
            self.assertEqual(len(segment_events[0]["properties"]["chat_referenced_documents"]), 0)
            self.assertEqual(
                segment_events[0]["properties"]["chat_system_prompt"],
                TestChatView.PAYLOAD_WITH_SYSTEM_PROMPT_OVERRIDE["system_prompt"],
            )
            self.assertFalse(segment_events[0]["properties"]["no_tools"])

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_operational_telemetry_with_no_tools_option(self):
        self.user.rh_user_has_seat = True
        self.user.organization = Organization.objects.get_or_create(id=1)[0]
        self.client.force_authenticate(user=self.user)
        with (
            patch.object(
                apps.get_app_config("ai"),
                "get_model_pipeline",
                Mock(
                    return_value=HttpStreamingChatBotPipeline(
                        mock_pipeline_config("http", model_id="granite-8b")
                    )
                ),
            ),
            self.assertLogs(logger="root", level="DEBUG") as log,
        ):
            r = self.query_with_no_error(TestChatView.PAYLOAD_WITH_NO_TOOLS_OPTION)
            self.assertEqual(r.status_code, HTTPStatus.OK)
            segment_events = self.extractSegmentEventsFromLog(log)
            # Verify that chat_prompt is not found
            self.assertNotIn("chat_prompt", segment_events[0]["properties"])
            self.assertEqual(segment_events[0]["properties"]["modelName"], "granite-8b")
            self.assertEqual(
                segment_events[0]["properties"]["chat_truncated"],
                TestChatView.JSON_RESPONSE["truncated"],
            )
            self.assertEqual(len(segment_events[0]["properties"]["chat_referenced_documents"]), 0)
            self.assertTrue(segment_events[0]["properties"]["no_tools"])

    def test_chat_rate_limit(self):
        # Call chat API five times using self.user
        for i in range(5):
            self.assert_test(TestChatView.VALID_PAYLOAD)
        try:
            username = "u" + "".join(random.choices(string.digits, k=5))
            password = "secret"
            email = "user2@example.com"
            self.user2 = get_user_model().objects.create_user(
                username=username,
                email=email,
                password=password,
            )
            (org, _) = Organization.objects.get_or_create(id=123, telemetry_opt_out=False)
            self.user2.organization = org
            self.user2.rh_internal = True
            # Call chart API five times using self.user2
            for i in range(5):
                self.assert_test(TestChatView.VALID_PAYLOAD, user=self.user2)
            # The next chat API call should be the 11th from two users and should receive a 429.
            self.assert_test(TestChatView.VALID_PAYLOAD, expected_status_code=429, user=self.user2)
        finally:
            if self.user2:
                self.user2.delete()

    def test_not_rh_internal_user(self):
        try:
            username = "u" + "".join(random.choices(string.digits, k=5))
            self.user2 = get_user_model().objects.create_user(
                username=username,
            )
            self.user2.organization = Organization.objects.get_or_create(
                id=123, telemetry_opt_out=False
            )[0]
            self.user2.rh_internal = False
            self.assert_test(TestChatView.VALID_PAYLOAD, expected_status_code=403, user=self.user2)
        finally:
            if self.user2:
                self.user2.delete()


class TestStreamingChatViewWithAnonymousUser(APIVersionTestCaseBase, WisdomServiceAPITestCaseBase):
    api_version = "v1"

    def setUp(self):
        super().setUp()

    def test(self):
        response = self.client.post(
            self.api_version_reverse("streaming_chat"), TestChatView.VALID_PAYLOAD, format="json"
        )
        self.assertEqual(response.status_code, 401)
