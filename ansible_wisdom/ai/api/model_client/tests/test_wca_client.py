from functools import wraps
from http import HTTPStatus
from unittest.mock import Mock, patch

import requests
from ai.api.aws.wca_secret_manager import (
    Suffixes,
    WcaSecretManager,
    WcaSecretManagerError,
)
from ai.api.model_client.exceptions import (
    ModelTimeoutError,
    WcaBadRequest,
    WcaCodeMatchFailure,
    WcaEmptyResponse,
    WcaInferenceFailure,
    WcaInvalidModelId,
    WcaKeyNotFound,
    WcaModelIdNotFound,
    WcaTokenFailure,
)
from ai.api.model_client.wca_client import (
    WCAClient,
    ibm_cloud_identity_token_hist,
    wca_codegen_hist,
    wca_codematch_hist,
)
from django.apps import apps
from django.test import override_settings
from requests.exceptions import HTTPError, ReadTimeout
from test_utils import WisdomServiceLogAwareTestCase


class MockResponse:
    def __init__(self, json, status_code):
        self._json = json
        self.status_code = status_code

    def json(self):
        return self._json

    def raise_for_status(self):
        return


def stub_wca_client(
    status_code,
    model_id,
    prompt="- name: install ffmpeg on Red Hat Enterprise Linux",
    response_data: dict = None,
):
    model_input = {
        "instances": [
            {
                "context": "null",
                "prompt": prompt,
            }
        ]
    }
    response = MockResponse(
        json=response_data,
        status_code=status_code,
    )
    model_client = WCAClient(inference_url='https://wca_api_url')
    model_client.session.post = Mock(return_value=response)
    model_client.get_api_key = Mock(return_value='org-api-key')
    model_client.get_model_id = Mock(return_value=model_id)
    model_client.get_token = Mock(return_value={"access_token": "abc"})
    return model_id, model_client, model_input


def assert_call_count_metrics(hist):
    def count_metrics_decorator(func):
        @wraps(func)
        def wrapped_function(*args, **kwargs):
            def get_count():
                for metric in hist.collect():
                    for sample in metric.samples:
                        if sample.name.endswith("_count"):
                            return sample.value
                return 0.0

            count_before = get_count()
            func(*args, **kwargs)
            count_after = get_count()
            assert count_after > count_before

        return wrapped_function

    return count_metrics_decorator


class TestWCAClient(WisdomServiceLogAwareTestCase):
    def setUp(self):
        super().setUp()
        self.secret_manager_patcher = patch.object(
            apps.get_app_config('ai'), '_wca_secret_manager', spec=WcaSecretManager
        )
        self.mock_secret_manager = self.secret_manager_patcher.start()

    def tearDown(self):
        self.secret_manager_patcher.stop()

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

    def test_seated_cannot_have_no_key(self):
        self.mock_secret_manager.get_secret.return_value = None
        wca_client = WCAClient(inference_url='http://example.com/')
        with self.assertRaises(WcaKeyNotFound):
            wca_client.get_api_key(True, '123')

    def test_seated_cannot_have_no_model(self):
        self.mock_secret_manager.get_secret.return_value = None
        wca_client = WCAClient(inference_url='http://example.com/')
        with self.assertRaises(WcaModelIdNotFound):
            wca_client.get_model_id(True, '123', None)

    def test_fatal_exception(self):
        """Test the logic to determine if an exception is fatal or not"""
        exc = Exception()
        b = WCAClient.fatal_exception(exc)
        self.assertFalse(b)

        exc = requests.RequestException()
        response = requests.Response()
        response.status_code = HTTPStatus.INTERNAL_SERVER_ERROR
        exc.response = response
        b = WCAClient.fatal_exception(exc)
        self.assertFalse(b)

        exc = requests.RequestException()
        response = requests.Response()
        response.status_code = HTTPStatus.TOO_MANY_REQUESTS
        exc.response = response
        b = WCAClient.fatal_exception(exc)
        self.assertFalse(b)

        exc = requests.RequestException()
        response = requests.Response()
        response.status_code = HTTPStatus.BAD_REQUEST
        exc.response = response
        b = WCAClient.fatal_exception(exc)
        self.assertTrue(b)


class TestWCACodegen(WisdomServiceLogAwareTestCase):
    def setUp(self):
        super().setUp()
        self.secret_manager_patcher = patch.object(
            apps.get_app_config('ai'), '_wca_secret_manager', spec=WcaSecretManager
        )
        self.mock_secret_manager = self.secret_manager_patcher.start()

    def tearDown(self):
        self.secret_manager_patcher.stop()

    @assert_call_count_metrics(hist=ibm_cloud_identity_token_hist)
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

    @assert_call_count_metrics(hist=ibm_cloud_identity_token_hist)
    def test_get_token_http_error(self):
        model_client = WCAClient(inference_url='http://example.com/')
        model_client.session.post = Mock(side_effect=HTTPError(404))
        with self.assertRaises(WcaTokenFailure):
            model_client.get_token("api-key")

    @assert_call_count_metrics(hist=wca_codegen_hist)
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

    @assert_call_count_metrics(hist=wca_codegen_hist)
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
        with self.assertRaises(ModelTimeoutError) as e:
            model_client.infer(model_input=model_input, model_id=model_id)
        self.assertEqual(e.exception.model_id, model_id)

    @assert_call_count_metrics(hist=wca_codegen_hist)
    def test_infer_http_error(self):
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
        model_client.session.post = Mock(side_effect=HTTPError(404))
        model_client.get_model_id = Mock(return_value=model_id)
        with self.assertRaises(WcaInferenceFailure) as e:
            model_client.infer(model_input=model_input, model_id=model_id)
        self.assertEqual(e.exception.model_id, model_id)

    @assert_call_count_metrics(hist=wca_codegen_hist)
    def test_infer_garbage_model_id(self):
        stub = stub_wca_client(400, "zavala")
        model_id, model_client, model_input = stub
        with self.assertRaises(WcaInvalidModelId) as e:
            model_client.infer(model_input=model_input, model_id=model_id)
        self.assertEqual(e.exception.model_id, model_id)

    @assert_call_count_metrics(hist=wca_codegen_hist)
    def test_infer_invalid_model_id_for_api_key(self):
        stub = stub_wca_client(403, "zavala")
        model_id, model_client, model_input = stub
        with self.assertRaises(WcaInvalidModelId) as e:
            model_client.infer(model_input=model_input, model_id=model_id)
        self.assertEqual(e.exception.model_id, model_id)

    @assert_call_count_metrics(hist=wca_codegen_hist)
    def test_infer_empty_response(self):
        stub = stub_wca_client(204, "zavala")
        model_id, model_client, model_input = stub
        with self.assertRaises(WcaEmptyResponse) as e:
            model_client.infer(model_input=model_input, model_id=model_id)
        self.assertEqual(e.exception.model_id, model_id)

    @assert_call_count_metrics(hist=wca_codegen_hist)
    def test_infer_preprocessed_multitask_prompt_error(self):
        # See https://issues.redhat.com/browse/AAP-16642
        stub = stub_wca_client(
            400,
            "zavala",
            "#Install Apache & say hello fred@redhat.com\n",
            {
                "detail": "(400, 'Failed to preprocess the "
                "prompt: mapping values are not allowed here"
            },
        )
        model_id, model_client, model_input = stub
        with self.assertRaises(WcaEmptyResponse):
            model_client.infer(model_input=model_input, model_id=model_id)


class TestWCACodematch(WisdomServiceLogAwareTestCase):
    def setUp(self):
        super().setUp()
        self.secret_manager_patcher = patch.object(
            apps.get_app_config('ai'), '_wca_secret_manager', spec=WcaSecretManager
        )
        self.mock_secret_manager = self.secret_manager_patcher.start()

    def tearDown(self):
        self.secret_manager_patcher.stop()

    @assert_call_count_metrics(hist=wca_codematch_hist)
    def test_codematch(self):
        model_id = "sample_model_name"
        suggestions = [
            "- name: install ffmpeg on Red Hat Enterprise Linux\n  "
            "ansible.builtin.package:\n    name:\n      - ffmpeg\n    state: present\n",
            "- name: This is another test",
        ]

        model_input = {"suggestions": suggestions}
        data = {
            "model_id": model_id,
            "input": suggestions,
        }
        token = {
            "access_token": "access_token",
            "refresh_token": "not_supported",
            "token_type": "Bearer",
            "expires_in": 3600,
            "expiration": 1691445310,
            "scope": "ibm openid",
        }
        client_response = {
            "code_matches": [
                {
                    "repo_name": "fiaasco.solr",
                    "repo_url": "https://galaxy.ansible.com/fiaasco/solr",
                    "path": "tasks/cores.yml",
                    "license": "mit",
                    "data_source_description": "Galaxy-R",
                    "score": 0.7182885,
                },
                {
                    "repo_name": "juju4.misp",
                    "repo_url": "https://galaxy.ansible.com/juju4/misp",
                    "path": "tasks/main.yml",
                    "license": "bsd-2-clause",
                    "data_source_description": "Galaxy-R",
                    "score": 0.71385884,
                },
            ]
        }
        response = MockResponse(
            json=client_response,
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

        result = model_client.codematch(model_input=model_input, model_id=model_id)

        model_client.get_token.assert_called_once()
        model_client.session.post.assert_called_once_with(
            "https://example.com/v1/wca/codematch/ansible",
            headers=headers,
            json=data,
            timeout=None,
        )
        self.assertEqual(result, client_response)

    @assert_call_count_metrics(hist=wca_codematch_hist)
    def test_codematch_timeout(self):
        model_id = "sample_model_name"
        suggestions = [
            "- name: install ffmpeg on Red Hat Enterprise Linux",
            "- name: This is another test",
        ]

        model_input = {"suggestions": suggestions}
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
        with self.assertRaises(ModelTimeoutError) as e:
            model_client.codematch(model_input=model_input, model_id=model_id)
        self.assertEqual(e.exception.model_id, model_id)

    @assert_call_count_metrics(hist=wca_codematch_hist)
    def test_codematch_http_error(self):
        model_id = "sample_model_name"
        model_input = {
            "instances": [
                {
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
        model_client.session.post = Mock(side_effect=HTTPError(404))
        model_client.get_model_id = Mock(return_value=model_id)
        with self.assertRaises(WcaCodeMatchFailure) as e:
            model_client.codematch(model_input=model_input, model_id=model_id)
        self.assertEqual(e.exception.model_id, model_id)

    @assert_call_count_metrics(hist=wca_codematch_hist)
    def test_codematch_bad_model_id(self):
        stub = stub_wca_client(400, "sample_model_name")
        model_id, model_client, model_input = stub
        with self.assertRaises(WcaInvalidModelId) as e:
            model_client.codematch(model_input=model_input, model_id=model_id)
        self.assertEqual(e.exception.model_id, model_id)

    @assert_call_count_metrics(hist=wca_codematch_hist)
    def test_codematch_invalid_model_id_for_api_key(self):
        stub = stub_wca_client(403, "sample_model_name")
        model_id, model_client, model_input = stub
        with self.assertRaises(WcaInvalidModelId) as e:
            model_client.codematch(model_input=model_input, model_id=model_id)
        self.assertEqual(e.exception.model_id, model_id)

    @assert_call_count_metrics(hist=wca_codematch_hist)
    def test_codematch_empty_response(self):
        stub = stub_wca_client(204, "sample_model_name")
        model_id, model_client, model_input = stub
        with self.assertRaises(WcaEmptyResponse) as e:
            model_client.codematch(model_input=model_input, model_id=model_id)
        self.assertEqual(e.exception.model_id, model_id)
