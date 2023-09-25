from unittest.mock import Mock, patch

from ai.api.aws.wca_secret_manager import (
    Suffixes,
    WcaSecretManager,
    WcaSecretManagerError,
)
from ai.api.model_client.exceptions import ModelTimeoutError
from ai.api.model_client.wca_client import (
    WcaBadRequest,
    WCAClient,
    WcaEmptyResponse,
    WcaInvalidModelId,
    WcaKeyNotFound,
    WcaModelIdNotFound,
)
from django.apps import apps
from django.test import override_settings
from requests.exceptions import ReadTimeout
from test_utils import WisdomServiceLogAwareTestCase

from ansible_wisdom.ai.api.model_client.wca.codematch import WCACodematchClient


class MockResponse:
    def __init__(self, json, status_code):
        self._json = json
        self.status_code = status_code

    def json(self):
        return self._json

    def raise_for_status(self):
        return


class TestWCAClient(WisdomServiceLogAwareTestCase):
    def setUp(self):
        super().setUp()
        self.secret_manager_patcher = patch.object(
            apps.get_app_config('ai'), '_wca_secret_manager', spec=WcaSecretManager
        )
        self.mock_secret_manager = self.secret_manager_patcher.start()

    def tearDown(self):
        self.secret_manager_patcher.stop()

    def stub_wca_client(self, status_code, model_name):
        model_input = {
            "instances": [
                {
                    "context": "null",
                    "prompt": "- name: install ffmpeg on Red Hat Enterprise Linux",
                }
            ]
        }
        response = MockResponse(
            json={},
            status_code=status_code,
        )
        model_client = WCAClient(inference_url='https://wca_api_url')
        model_client.session.post = Mock(return_value=response)
        model_client.get_api_key = Mock(return_value='org-api-key')
        model_client.get_model_id = Mock(return_value=model_name)
        model_client.get_token = Mock(return_value={"access_token": "abc"})
        return model_name, model_client, model_input

    @override_settings(ANSIBLE_WCA_FREE_API_KEY='abcdef')
    def test_get_api_key_without_seat(self):
        model_client = WCAClient(inference_url='http://example.com/')
        api_key = model_client.get_api_key(False, None)
        self.assertEqual(api_key, 'abcdef')

    @override_settings(ANSIBLE_WCA_FREE_API_KEY='abcdef')
    def test_get_api_key_with_seat_without_org_id(self):
        model_client = WCAClient(inference_url='http://example.com/')
        api_key = model_client.get_api_key(True, None)
        self.assertEqual(api_key, 'abcdef')

    def test_get_api_key_from_aws(self):
        secret_value = '12345'
        self.mock_secret_manager.get_secret.return_value = {
            "SecretString": secret_value,
            "CreatedDate": "xxx",
        }
        model_client = WCAClient(inference_url='http://example.com/')
        api_key = model_client.get_api_key(True, '123')
        self.assertEqual(api_key, secret_value)
        self.mock_secret_manager.get_secret.assert_called_once_with('123', Suffixes.API_KEY)

    def test_get_api_key_from_aws_error(self):
        self.mock_secret_manager.get_secret.side_effect = WcaSecretManagerError
        model_client = WCAClient(inference_url='http://example.com/')
        with self.assertRaises(WcaSecretManagerError):
            model_client.get_api_key(True, '123')

    @override_settings(ANSIBLE_WCA_FREE_MODEL_ID='free')
    def test_seatless_get_free_model(self):
        wca_client = WCAClient(inference_url='http://example.com/')
        model_id = wca_client.get_model_id(False, None, None)
        self.assertEqual(model_id, 'free')

    def test_seatless_cannot_pick_model(self):
        wca_client = WCAClient(inference_url='http://example.com/')
        with self.assertRaises(WcaBadRequest):
            wca_client.get_model_id(False, None, 'some-model')

    def test_seated_get_org_default_model(self):
        self.mock_secret_manager.get_secret.return_value = {
            "SecretString": "org-model",
            "CreatedDate": "xxx",
        }
        wca_client = WCAClient(inference_url='http://example.com/')
        model_id = wca_client.get_model_id(True, '123', None)
        self.assertEqual(model_id, 'org-model')
        self.mock_secret_manager.get_secret.assert_called_once_with('123', Suffixes.MODEL_ID)

    def test_seated_can_pick_model(self):
        wca_client = WCAClient(inference_url='http://example.com/')
        model_id = wca_client.get_model_id(True, '123', 'model-i-pick')
        self.assertEqual(model_id, 'model-i-pick')

    def test_seated_cannot_have_no_model(self):
        self.mock_secret_manager.get_secret.return_value = None
        wca_client = WCAClient(inference_url='http://example.com/')
        with self.assertRaises(WcaBadRequest):
            wca_client.get_model_id(True, '123', None)


class TestWCACodegenClient(WisdomServiceLogAwareTestCase):
    def setUp(self):
        super().setUp()
        self.secret_manager_patcher = patch.object(
            apps.get_app_config('ai'), '_wca_secret_manager', spec=WcaSecretManager
        )
        self.mock_secret_manager = self.secret_manager_patcher.start()

    def tearDown(self):
        self.secret_manager_patcher.stop()

    def test_get_token(self):
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        data = {"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": "abcdef"}
        response = MockResponse(
            json={
                "access_token": "access_token",
                "refresh_token": "not_supported",
                "token_type": "Bearer",
                "expires_in": 3600,
                "expiration": 1691445310,
                "scope": "ibm openid",
            },
            status_code=200,
        )

        model_client = WCAClient(inference_url='http://example.com/')
        model_client.session.post = Mock(return_value=response)
        model_client.get_token('abcdef')

        model_client.session.post.assert_called_once_with(
            "https://iam.cloud.ibm.com/identity/token",
            headers=headers,
            data=data,
        )

    def test_infer(self):
        model_id = "zavala"
        context = "null"
        prompt = "- name: install ffmpeg on Red Hat Enterprise Linux"

        model_input = {
            "instances": [
                {
                    "context": context,
                    "prompt": prompt,
                }
            ]
        }
        data = {
            "model_id": model_id,
            "prompt": f"{context}{prompt}\n",
        }
        token = {
            "access_token": "access_token",
            "refresh_token": "not_supported",
            "token_type": "Bearer",
            "expires_in": 3600,
            "expiration": 1691445310,
            "scope": "ibm openid",
        }
        predictions = {"predictions": ["      ansible.builtin.apt:\n        name: apache2"]}
        response = MockResponse(
            json=predictions,
            status_code=200,
        )

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token['access_token']}",
        }

        model_client = WCAClient(inference_url='https://example.com')
        model_client.session.post = Mock(return_value=response)
        model_client.get_token = Mock(return_value=token)
        model_client.get_model_id = Mock(return_value=model_id)

        result = model_client.infer(model_input=model_input, model_id=model_id)

        model_client.get_token.assert_called_once()
        model_client.session.post.assert_called_once_with(
            "https://example.com/v1/wca/codegen/ansible",
            headers=headers,
            json=data,
            timeout=None,
        )
        self.assertEqual(result, predictions)

    def test_infer_timeout(self):
        model_id = "zavala"
        model_input = {
            "instances": [
                {
                    "context": "null",
                    "prompt": "- name: install ffmpeg on Red Hat Enterprise Linux",
                }
            ]
        }
        token = {
            "access_token": "access_token",
            "refresh_token": "not_supported",
            "token_type": "Bearer",
            "expires_in": 3600,
            "expiration": 1691445310,
            "scope": "ibm openid",
        }
        model_client = WCAClient(inference_url='https://example.com')
        model_client.get_token = Mock(return_value=token)
        model_client.session.post = Mock(side_effect=ReadTimeout())
        model_client.get_model_id = Mock(return_value=model_id)
        with self.assertRaises(ModelTimeoutError):
            model_client.infer(model_input=model_input, model_id=model_id)

    def test_infer_garbage_model_id(self):
        stub = self.stub_wca_client(400, "zavala")
        model_id, model_client, model_input = stub
        with self.assertRaises(WcaInvalidModelId):
            model_client.infer(model_input=model_input, model_id=model_id)

    def test_infer_invalid_model_id_for_api_key(self):
        stub = self.stub_wca_client(403, "zavala")
        model_id, model_client, model_input = stub
        with self.assertRaises(WcaInvalidModelId):
            model_client.infer(model_input=model_input, model_id=model_id)

    def test_infer_empty_response(self):
        stub = self.stub_wca_client(204, "zavala")
        model_id, model_client, model_input = stub
        with self.assertRaises(WcaEmptyResponse):
            model_client.infer(model_input=model_input, model_id=model_id)


class TestWCACodematchClient(WisdomServiceLogAwareTestCase):
    def setUp(self):
        super().setUp()
        self.secret_manager_patcher = patch.object(
            apps.get_app_config('ai'), '_wca_secret_manager', spec=WcaSecretManager
        )
        self.mock_secret_manager = self.secret_manager_patcher.start()

    def tearDown(self):
        self.secret_manager_patcher.stop()

    def test_get_token(self):
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        data = {"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": "abcdef"}
        response = MockResponse(
            json={
                "access_token": "access_token",
                "refresh_token": "not_supported",
                "token_type": "Bearer",
                "expires_in": 3600,
                "expiration": 1691445310,
                "scope": "ibm openid",
            },
            status_code=200,
        )

        model_client = WCACodematchClient(inference_url='http://example.com/')
        model_client.session.post = Mock(return_value=response)
        model_client.get_token('abcdef')

        model_client.session.post.assert_called_once_with(
            "https://iam.cloud.ibm.com/identity/token",
            headers=headers,
            data=data,
        )

    def test_infer(self):
        model_name = "sample_model_name"
        prompt = "- name: install ffmpeg on Red Hat Enterprise Linux"

        model_input = {
            "instances": [
                {
                    "prompt": prompt,
                }
            ]
        }
        data = {
            "model_id": model_name,
            "input": [f"{prompt}"],
        }
        token = {
            "access_token": "access_token",
            "refresh_token": "not_supported",
            "token_type": "Bearer",
            "expires_in": 3600,
            "expiration": 1691445310,
            "scope": "ibm openid",
        }
        client_response = {"attributions": ["      ansible.builtin.apt:\n        name: apache2"]}
        response = MockResponse(
            json=client_response,
            status_code=200,
        )

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token['access_token']}",
        }

        model_client = WCACodematchClient(inference_url='https://example.com')
        model_client.session.post = Mock(return_value=response)
        model_client.get_token = Mock(return_value=token)
        model_client.get_model_id = Mock(return_value=model_name)

        result = model_client.infer(model_input=model_input, model_name=model_name)

        model_client.get_token.assert_called_once()
        model_client.session.post.assert_called_once_with(
            "https://example.com/v1/wca/codematch/ansible",
            headers=headers,
            json=data,
            timeout=None,
        )
        self.assertEqual(result, client_response)

    def test_infer_timeout(self):
        model_name = "sample_model_name"
        model_input = {
            "instances": [
                {
                    "context": "null",
                    "prompt": "- name: install ffmpeg on Red Hat Enterprise Linux",
                }
            ]
        }
        token = {
            "access_token": "access_token",
            "refresh_token": "not_supported",
            "token_type": "Bearer",
            "expires_in": 3600,
            "expiration": 1691445310,
            "scope": "ibm openid",
        }
        model_client = WCACodematchClient(inference_url='https://example.com')
        model_client.get_token = Mock(return_value=token)
        model_client.session.post = Mock(side_effect=ReadTimeout())
        model_client.get_model_id = Mock(return_value=model_name)
        with self.assertRaises(ModelTimeoutError):
            model_client.infer(model_input=model_input, model_name=model_name)
