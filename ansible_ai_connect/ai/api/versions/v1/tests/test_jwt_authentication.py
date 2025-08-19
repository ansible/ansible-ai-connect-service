import json
import random
import string
import uuid
from datetime import datetime, timedelta
from http import HTTPStatus
from unittest import mock
from unittest.mock import Mock, patch

import jwt
import requests
from ansible_base.rbac.claims import get_claims_hash
from ansible_base.resource_registry.models.service_identifier import service_id
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.apps import apps
from django.test import override_settings
from rest_framework.test import APITransactionTestCase

from ansible_ai_connect.ai.api.model_pipelines.http.pipelines import HttpChatBotPipeline
from ansible_ai_connect.ai.api.model_pipelines.tests import mock_pipeline_config
from ansible_ai_connect.ai.api.versions.v1.test_base import API_VERSION
from ansible_ai_connect.test_utils import APIVersionTestCaseBase
from ansible_ai_connect.users.models import User

# Generate public and private keys for testing
private_key = rsa.generate_private_key(
    public_exponent=65537, key_size=4096, backend=default_backend()
)
test_encryption_private_key = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.TraditionalOpenSSL,
    encryption_algorithm=serialization.NoEncryption(),
).decode()
test_encryption_public_key = (
    private_key.public_key()
    .public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    .decode()
)

ISSUER = "ansible-issuer"
AUDIENCE = "ansible-services"

ANSIBLE_AI_MODEL_MESH_CONFIG = {
    "ModelPipelineChatBot": {
        "provider": "http",
        "config": {
            "inference_url": "http://localhost:8080",
            "model_id": "granite-3.3-8b-instruct",
            "enable_health_check": True,
            "mcp_servers": [
                {"name": "mcp::aap-controller", "type": "controller"},
                {"name": "mcp::aap-gateway", "type": "gateway"},
                {"name": "mcp::aap-lightspeed", "type": "lightspeed"},
            ],
        },
    },
}


@override_settings(ANSIBLE_BASE_JWT_KEY=test_encryption_public_key)
@patch.object(
    apps.get_app_config("ai"),
    "get_model_pipeline",
    Mock(
        return_value=HttpChatBotPipeline(
            mock_pipeline_config(
                "http", **ANSIBLE_AI_MODEL_MESH_CONFIG["ModelPipelineChatBot"]["config"]
            ),
        )
    ),
)
class TestJWTAuthentication(APIVersionTestCaseBase, APITransactionTestCase):
    api_version = API_VERSION

    def setUp(self):
        super().setUp()
        self.username = "u" + "".join(random.choices(string.digits, k=5))
        self.email = "user@example.com"
        self.user_id = str(uuid.uuid4())
        self.unencrypted_token = {
            "version": "1",
            "iss": ISSUER,
            "exp": int((datetime.now() + timedelta(minutes=10)).timestamp()),
            "aud": AUDIENCE,
            "sub": self.user_id,
            "service_id": service_id(),
            "user_data": {
                "username": self.username,
                "first_name": "User",
                "last_name": "AAP",
                "email": self.email,
                "is_superuser": False,
            },
            "claims_hash": get_claims_hash({"id": self.user_id, "username": self.username}),
            "objects": {},
            "object_roles": {},
            "global_roles": [],
        }
        self.encrypted_token = jwt.encode(
            self.unencrypted_token, test_encryption_private_key, algorithm="RS256"
        )

    def tearDown(self):
        User.objects.filter(username=self.username).delete()
        super().tearDown()

    @property
    def jwt_client(self):
        return self.client_class(headers={"X-DAB-JW-TOKEN": self.encrypted_token})

    def test_user_authentication(self):
        response = self.jwt_client.get(self.api_version_reverse("me"))
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(self.username, response.data.get("username"))
        self.assertTrue(response.wsgi_request.user.aap_user)

    @override_settings(CHATBOT_DEFAULT_PROVIDER="wisdom")
    @mock.patch.object(requests, "post")
    def test_chat_authentication(self, mock_requests_post):

        class MockRequestsResponse:
            def __init__(self, json_data, status_code):
                self.json_data = json_data
                self.status_code = status_code
                self.text = json.dumps(json_data)

            def json(self):
                return self.json_data

        expected_response = {
            "response": "Hello world!",
            "conversation_id": "19d6745f-5373-4c43-85a3-47d4df04841a",
            "truncated": False,
            "referenced_documents": [],
        }
        mock_requests_post.return_value = MockRequestsResponse(
            expected_response,
            HTTPStatus.OK,
        )

        response = self.jwt_client.post(
            self.api_version_reverse("chat"), {"query": "Hello"}, format="json"
        )

        mock_requests_post.assert_called_once()
        _, kwargs = mock_requests_post.call_args

        headers = kwargs.get("headers", None)
        self.assertIsNotNone(headers)

        mcp_headers_string = headers.get("MCP-HEADERS", None)
        self.assertIsNotNone(headers)

        expected_mcp_headers = {
            "mcp::aap-controller": {"X-DAB-JW-TOKEN": self.encrypted_token},
            "mcp::aap-lightspeed": {"X-DAB-JW-TOKEN": self.encrypted_token},
        }
        mcp_headers = json.loads(mcp_headers_string)

        self.assertDictEqual(mcp_headers, expected_mcp_headers)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertDictEqual(response.data, expected_response)
