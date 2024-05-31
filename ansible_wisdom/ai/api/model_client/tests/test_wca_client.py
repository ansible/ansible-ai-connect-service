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

import base64
import uuid
from datetime import datetime
from functools import wraps
from http import HTTPStatus
from unittest.mock import ANY, Mock, patch

import django.utils.timezone
import requests
from django.test import TestCase, override_settings
from prometheus_client import Counter, Histogram
from requests.auth import HTTPBasicAuth
from requests.exceptions import HTTPError, ReadTimeout

from ansible_ai_connect.ai.api.aws.wca_secret_manager import (
    DummySecretEntry,
    DummySecretManager,
    Suffixes,
    WcaSecretManagerError,
)
from ansible_ai_connect.ai.api.model_client.exceptions import (
    ModelTimeoutError,
    WcaBadRequest,
    WcaCodeMatchFailure,
    WcaEmptyResponse,
    WcaInferenceFailure,
    WcaInvalidModelId,
    WcaKeyNotFound,
    WcaModelIdNotFound,
    WcaNoDefaultModelId,
    WcaSuggestionIdCorrelationFailure,
    WcaTokenFailure,
)
from ansible_ai_connect.ai.api.model_client.wca_client import (
    WCA_REQUEST_ID_HEADER,
    WCAClient,
    WCAOnPremClient,
    ibm_cloud_identity_token_hist,
    ibm_cloud_identity_token_retry_counter,
    wca_codegen_hist,
    wca_codegen_retry_counter,
    wca_codematch_hist,
    wca_codematch_retry_counter,
)
from ansible_ai_connect.test_utils import (
    WisdomAppsBackendMocking,
    WisdomServiceLogAwareTestCase,
)

DEFAULT_SUGGESTION_ID = uuid.uuid4()


class MockResponse:
    def __init__(self, json, status_code, headers=None, text=None):
        self._json = json
        self.status_code = status_code
        self.headers = {} if headers is None else headers
        self.text = text

    def json(self):
        return self._json

    def text(self):
        return self.text

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
        headers={WCA_REQUEST_ID_HEADER: str(DEFAULT_SUGGESTION_ID)},
    )
    model_client = WCAClient(inference_url='https://wca_api_url')
    model_client.session.post = Mock(return_value=response)
    model_client.get_api_key = Mock(return_value='org-api-key')
    model_client.get_model_id = Mock(return_value=model_id)
    model_client.get_token = Mock(return_value={"access_token": "abc"})
    return model_id, model_client, model_input


def assert_call_count_metrics(metric):
    def count_metrics_decorator(func):
        @wraps(func)
        def wrapped_function(*args, **kwargs):
            def get_count():
                for m in metric.collect():
                    for sample in m.samples:
                        if isinstance(metric, Histogram) and sample.name.endswith("_count"):
                            return sample.value
                        if isinstance(metric, Counter) and sample.name.endswith("_total"):
                            return sample.value
                return 0.0

            count_before = get_count()
            func(*args, **kwargs)
            count_after = get_count()
            assert count_after > count_before

        return wrapped_function

    return count_metrics_decorator


@override_settings(WCA_SECRET_BACKEND_TYPE='dummy')
@override_settings(ANSIBLE_AI_MODEL_MESH_API_KEY=None)
@override_settings(ANSIBLE_AI_MODEL_MESH_MODEL_NAME=None)
class TestWCAClient(WisdomAppsBackendMocking, WisdomServiceLogAwareTestCase):
    @override_settings(WCA_SECRET_DUMMY_SECRETS='11009103:my-key<sep>my-optimized-model')
    def test_mock_wca_get_api_key(self):
        model_client = WCAClient(inference_url='http://example.com/')
        api_key = model_client.get_api_key(11009103)
        self.assertEqual(api_key, 'my-key')

    def test_get_api_key_without_org_id(self):
        model_client = WCAClient(inference_url='http://example.com/')
        with self.assertRaises(WcaKeyNotFound):
            model_client.get_api_key(None)

    @override_settings(WCA_SECRET_DUMMY_SECRETS='123:12345<sep>my-model')
    def test_get_api_key_from_aws(self):
        secret_value = '12345'
        model_client = WCAClient(inference_url='http://example.com/')
        api_key = model_client.get_api_key(123)
        self.assertEqual(api_key, secret_value)

    def test_get_api_key_from_aws_error(self):
        m = Mock()
        m.get_secret.side_effect = WcaSecretManagerError
        self.mock_wca_secret_manager_with(m)
        model_client = WCAClient(inference_url='http://example.com/')
        with self.assertRaises(WcaSecretManagerError):
            model_client.get_api_key('123')

    @override_settings(ANSIBLE_AI_MODEL_MESH_API_KEY='key')
    def test_get_api_key_with_environment_override(self):
        model_client = WCAClient(inference_url='http://example.com/')
        api_key = model_client.get_api_key(123)
        self.assertEqual(api_key, 'key')

    @override_settings(WCA_SECRET_DUMMY_SECRETS='123:my-key<sep>my-great-model')
    def test_get_model_id_with_empty_model(self):
        wca_client = WCAClient(inference_url='http://example.com/')
        model_id = wca_client.get_model_id(organization_id=123, requested_model_id='')
        self.assertEqual(model_id, 'my-great-model')

    @override_settings(WCA_SECRET_DUMMY_SECRETS='123:my-key<sep>org-model')
    def test_get_model_id_get_org_default_model(self):
        wca_client = WCAClient(inference_url='http://example.com/')
        model_id = wca_client.get_model_id(123, None)
        self.assertEqual(model_id, 'org-model')

    def test_get_model_id_with_model_override(self):
        wca_client = WCAClient(inference_url='http://example.com/')
        model_id = wca_client.get_model_id(123, 'model-i-pick')
        self.assertEqual(model_id, 'model-i-pick')

    def test_get_model_id_without_org_id(self):
        model_client = WCAClient(inference_url='http://example.com/')
        with self.assertRaises(WcaNoDefaultModelId):
            model_client.get_model_id(None, None)

    @override_settings(WCA_SECRET_DUMMY_SECRETS='123:')
    def test_get_api_key_org_cannot_have_no_key(self):
        wca_client = WCAClient(inference_url='http://example.com/')
        with self.assertRaises(WcaKeyNotFound):
            wca_client.get_api_key(123)

    @override_settings(WCA_SECRET_DUMMY_SECRETS='')
    def test_get_model_id_org_cannot_have_no_model(self):
        wca_client = WCAClient(inference_url='http://example.com/')
        with self.assertRaises(WcaModelIdNotFound):
            wca_client.get_model_id(123, None)

    @override_settings(ANSIBLE_AI_MODEL_MESH_MODEL_NAME='gemini')
    def test_model_id_with_environment_override(self):
        wca_client = WCAClient(inference_url='http://example.com/')
        model_id = wca_client.get_model_id(123, None)
        self.assertEqual(model_id, 'gemini')

    @override_settings(ANSIBLE_AI_MODEL_MESH_MODEL_NAME='gemini')
    def test_model_id_with_environment_and_user_override(self):
        wca_client = WCAClient(inference_url='http://example.com/')
        model_id = wca_client.get_model_id(123, 'bard')
        self.assertEqual(model_id, 'bard')

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


@override_settings(WCA_SECRET_BACKEND_TYPE='dummy')
@override_settings(ANSIBLE_AI_MODEL_MESH_API_KEY=None)
@override_settings(ANSIBLE_AI_MODEL_MESH_MODEL_NAME=None)
@override_settings(ENABLE_ANSIBLE_LINT_POSTPROCESS=False)
class TestWCAClientExpGen(WisdomAppsBackendMocking, WisdomServiceLogAwareTestCase):
    def setUp(self):
        super().setUp()
        wca_client = WCAClient(inference_url='http://example.com/')
        wca_client.get_api_key = Mock(return_value="some-key")
        wca_client.get_token = Mock(return_value={"access_token": "a-token"})
        wca_client.get_model_id = Mock(return_value="a-random-model")
        wca_client.session = Mock()
        response = Mock
        response.text = '{"playbook": "Oh!", "outline": "Ahh!", "explanation": "!Óh¡"}'
        wca_client.session.post.return_value = response
        self.wca_client = wca_client

    def test_playbook_gen(self):
        request = Mock()
        playbook, outline = self.wca_client.generate_playbook(
            request, text="Install Wordpress", create_outline=True
        )
        self.assertEqual(playbook, "Oh!")
        self.assertEqual(outline, "Ahh!")

    def test_playbook_exp(self):
        request = Mock()
        explanation = self.wca_client.explain_playbook(request, content="Some playbook")
        self.assertEqual(explanation, "!Óh¡")

    def test_playbook_gen_no_org(self):
        request = Mock()
        request.user.organization = None
        self.wca_client.generate_playbook(request, text="Install Wordpress")
        self.wca_client.get_api_key.assert_called_with(None)

    def test_playbook_exp_no_org(self):
        request = Mock()
        request.user.organization = None
        self.wca_client.explain_playbook(request, content="Some playbook")
        self.wca_client.get_api_key.assert_called_with(None)

    @override_settings(ENABLE_ANSIBLE_LINT_POSTPROCESS=True)
    def test_playbook_gen_with_lint(self):
        fake_linter = Mock()
        fake_linter.run_linter.return_value = "I'm super fake!"
        self.mock_ansible_lint_caller_with(fake_linter)
        playbook, outline = self.wca_client.generate_playbook(
            request=Mock(), text="Install Wordpress", create_outline=True
        )
        self.assertEqual(playbook, "I'm super fake!")
        self.assertEqual(outline, "Ahh!")

    @override_settings(ENABLE_ANSIBLE_LINT_POSTPROCESS=True)
    def test_playbook_gen_when_is_not_initialized(self):
        self.mock_ansible_lint_caller_with(None)
        playbook, outline = self.wca_client.generate_playbook(
            request=Mock(), text="Install Wordpress", create_outline=True
        )
        # Ensure nothing was done
        self.assertEqual(playbook, "Oh!")


@override_settings(ANSIBLE_WCA_RETRY_COUNT=1)
@override_settings(WCA_SECRET_BACKEND_TYPE="dummy")
@override_settings(ANSIBLE_AI_MODEL_MESH_API_TIMEOUT=None)
@override_settings(ANSIBLE_WCA_IDP_URL="https://iam.cloud.ibm.com/identity")
@override_settings(ANSIBLE_WCA_IDP_LOGIN=None)
@override_settings(ANSIBLE_WCA_IDP_PASSWORD=None)
class TestWCACodegen(WisdomAppsBackendMocking, WisdomServiceLogAwareTestCase):
    @assert_call_count_metrics(metric=ibm_cloud_identity_token_hist)
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
            auth=None,
        )

    @override_settings(ANSIBLE_WCA_IDP_URL='http://some-different-idp')
    @override_settings(ANSIBLE_WCA_IDP_LOGIN='jimmy')
    @override_settings(ANSIBLE_WCA_IDP_PASSWORD='jimmy')
    @assert_call_count_metrics(metric=ibm_cloud_identity_token_hist)
    def test_get_token_with_auth(self):
        model_client = WCAClient(inference_url='http://example.com/')
        model_client.session.post = Mock()
        basic = HTTPBasicAuth('jimmy', 'jimmy')

        model_client.get_token('abcdef')

        model_client.session.post.assert_called_once_with(
            "http://some-different-idp/token",
            headers=ANY,
            data=ANY,
            auth=basic,
        )

    @assert_call_count_metrics(metric=ibm_cloud_identity_token_hist)
    @assert_call_count_metrics(metric=ibm_cloud_identity_token_retry_counter)
    def test_get_token_http_error(self):
        model_client = WCAClient(inference_url='http://example.com/')
        model_client.session.post = Mock(side_effect=HTTPError(404))
        with self.assertRaises(WcaTokenFailure):
            model_client.get_token("api-key")

    @assert_call_count_metrics(metric=wca_codegen_hist)
    def test_infer(self):
        self._do_inference(
            suggestion_id=str(DEFAULT_SUGGESTION_ID), request_id=str(DEFAULT_SUGGESTION_ID)
        )

    @assert_call_count_metrics(metric=wca_codegen_hist)
    def test_infer_organization_id_is_none(self):
        self._do_inference(
            suggestion_id=str(DEFAULT_SUGGESTION_ID),
            organization_id=None,
            request_id=str(DEFAULT_SUGGESTION_ID),
        )

    @assert_call_count_metrics(metric=wca_codegen_hist)
    def test_infer_without_suggestion_id(self):
        self._do_inference(suggestion_id=None, request_id=str(DEFAULT_SUGGESTION_ID))

    @assert_call_count_metrics(metric=wca_codegen_hist)
    def test_infer_without_request_id_header(self):
        self._do_inference(suggestion_id=str(DEFAULT_SUGGESTION_ID), request_id=None)

    def _do_inference(
        self,
        suggestion_id=None,
        organization_id=123,
        request_id=None,
        prompt=None,
        codegen_prompt=None,
    ):
        model_id = "zavala"
        api_key = "abc123"
        context = ""
        prompt = prompt if prompt else "- name: install ffmpeg on Red Hat Enterprise Linux"

        model_input = {
            "instances": [
                {
                    "context": context,
                    "prompt": prompt,
                    "organization_id": organization_id,
                }
            ]
        }
        codegen_data = {
            "model_id": model_id,
            "prompt": codegen_prompt if codegen_prompt else f"{context}{prompt}\n",
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
            headers={WCA_REQUEST_ID_HEADER: request_id},
        )

        requestHeaders = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token['access_token']}",
            WCA_REQUEST_ID_HEADER: suggestion_id,
        }

        model_client = WCAClient(inference_url='https://example.com')
        model_client.session.post = Mock(return_value=response)
        model_client.get_token = Mock(return_value=token)
        model_client.get_model_id = Mock(return_value=model_id)
        model_client.get_api_key = Mock(return_value=api_key)

        result = model_client.infer(
            model_input=model_input,
            model_id=model_id,
            suggestion_id=suggestion_id,
        )

        model_client.get_token.assert_called_once()
        model_client.session.post.assert_called_once_with(
            "https://example.com/v1/wca/codegen/ansible",
            headers=requestHeaders,
            json=codegen_data,
            timeout=None,
        )
        self.assertEqual(result, predictions)

    @assert_call_count_metrics(metric=wca_codegen_hist)
    def test_infer_timeout(self):
        model_id = "zavala"
        api_key = "abc123"
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
        model_client.get_api_key = Mock(return_value=api_key)
        with self.assertRaises(ModelTimeoutError) as e:
            model_client.infer(
                model_input=model_input, model_id=model_id, suggestion_id=DEFAULT_SUGGESTION_ID
            )
        self.assertEqual(e.exception.model_id, model_id)

    @assert_call_count_metrics(metric=wca_codegen_hist)
    @assert_call_count_metrics(metric=wca_codegen_retry_counter)
    def test_infer_http_error(self):
        model_id = "zavala"
        api_key = "abc123"
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
        model_client.get_api_key = Mock(return_value=api_key)
        with self.assertRaises(WcaInferenceFailure) as e:
            model_client.infer(
                model_input=model_input, model_id=model_id, suggestion_id=DEFAULT_SUGGESTION_ID
            )
        self.assertEqual(e.exception.model_id, model_id)

    @assert_call_count_metrics(metric=wca_codegen_hist)
    def test_infer_request_id_correlation_failure(self):
        model_id = "zavala"
        api_key = "abc123"
        model_input = {
            "instances": [
                {
                    "context": "",
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
        predictions = {"predictions": ["      ansible.builtin.apt:\n        name: apache2"]}
        response = MockResponse(
            json=predictions,
            status_code=200,
            headers={WCA_REQUEST_ID_HEADER: 'some-other-uuid'},
        )
        model_client = WCAClient(inference_url='https://example.com')
        model_client.session.post = Mock(return_value=response)
        model_client.get_token = Mock(return_value=token)
        model_client.get_model_id = Mock(return_value=model_id)
        model_client.get_api_key = Mock(return_value=api_key)

        with self.assertRaises(WcaSuggestionIdCorrelationFailure) as e:
            model_client.infer(
                model_input=model_input, model_id=model_id, suggestion_id=DEFAULT_SUGGESTION_ID
            )
        self.assertEqual(e.exception.model_id, model_id)

    @assert_call_count_metrics(metric=wca_codegen_hist)
    def test_infer_garbage_model_id(self):
        stub = stub_wca_client(
            400,
            "zavala",
            response_data={"error": "Bad request: [('value_error', ('body', 'model_id'))]"},
        )
        model_id, model_client, model_input = stub
        with self.assertRaises(WcaInvalidModelId) as e:
            model_client.infer(
                model_input=model_input, model_id=model_id, suggestion_id=DEFAULT_SUGGESTION_ID
            )
        self.assertEqual(e.exception.model_id, model_id)

    @assert_call_count_metrics(metric=wca_codegen_hist)
    def test_infer_invalid_model_id_for_api_key(self):
        stub = stub_wca_client(403, "zavala")
        model_id, model_client, model_input = stub
        with self.assertRaises(WcaInvalidModelId) as e:
            model_client.infer(
                model_input=model_input, model_id=model_id, suggestion_id=DEFAULT_SUGGESTION_ID
            )
        self.assertEqual(e.exception.model_id, model_id)

    @assert_call_count_metrics(metric=wca_codegen_hist)
    def test_infer_empty_response(self):
        stub = stub_wca_client(204, "zavala")
        model_id, model_client, model_input = stub
        with self.assertRaises(WcaEmptyResponse) as e:
            model_client.infer(
                model_input=model_input, model_id=model_id, suggestion_id=DEFAULT_SUGGESTION_ID
            )
        self.assertEqual(e.exception.model_id, model_id)

    @assert_call_count_metrics(metric=wca_codegen_hist)
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
        with self.assertRaises(WcaBadRequest):
            model_client.infer(
                model_input=model_input, model_id=model_id, suggestion_id=DEFAULT_SUGGESTION_ID
            )

    @assert_call_count_metrics(metric=wca_codegen_hist)
    def test_infer_multitask_with_task_preamble(self):
        self._do_inference(
            suggestion_id=str(DEFAULT_SUGGESTION_ID),
            request_id=str(DEFAULT_SUGGESTION_ID),
            prompt="# - name: install ffmpeg on Red Hat Enterprise Linux",
            codegen_prompt="# install ffmpeg on red hat enterprise linux\n",
        )


@override_settings(ANSIBLE_AI_MODEL_MESH_API_TIMEOUT=None)
class TestWCACodematch(WisdomServiceLogAwareTestCase):
    def setUp(self):
        super().setUp()
        self.now_patcher = patch.object(django.utils.timezone, 'now', return_value=datetime.now())
        self.mocked_now = self.now_patcher.start()

    def tearDown(self):
        self.now_patcher.stop()
        super().tearDown()

    @assert_call_count_metrics(metric=wca_codematch_hist)
    def test_codematch(self):
        model_id = "sample_model_name"
        api_key = "abc123"
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

        code_matches = {
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

        client_response = (model_id, code_matches)
        response = MockResponse(json=code_matches, status_code=200)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token['access_token']}",
        }

        model_client = WCAClient(inference_url='https://example.com')
        model_client.session.post = Mock(return_value=response)
        model_client.get_token = Mock(return_value=token)
        model_client.get_model_id = Mock(return_value=model_id)
        model_client.get_api_key = Mock(return_value=api_key)

        result = model_client.codematch(model_input=model_input, model_id=model_id)

        model_client.get_token.assert_called_once()
        model_client.session.post.assert_called_once_with(
            "https://example.com/v1/wca/codematch/ansible",
            headers=headers,
            json=data,
            timeout=None,
        )
        self.assertEqual(result, client_response)

    @assert_call_count_metrics(metric=wca_codematch_hist)
    def test_codematch_timeout(self):
        model_id = "sample_model_name"
        api_key = "abc123"
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
        model_client.get_api_key = Mock(return_value=api_key)
        with self.assertRaises(ModelTimeoutError) as e:
            model_client.codematch(model_input=model_input, model_id=model_id)
        self.assertEqual(e.exception.model_id, model_id)

    @assert_call_count_metrics(metric=wca_codematch_hist)
    @assert_call_count_metrics(metric=wca_codematch_retry_counter)
    def test_codematch_http_error(self):
        model_id = "sample_model_name"
        api_key = "abc123"
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
        model_client.get_api_key = Mock(return_value=api_key)
        with self.assertRaises(WcaCodeMatchFailure) as e:
            model_client.codematch(model_input=model_input, model_id=model_id)
        self.assertEqual(e.exception.model_id, model_id)

    @assert_call_count_metrics(metric=wca_codematch_hist)
    def test_codematch_bad_model_id(self):
        stub = stub_wca_client(
            400,
            "sample_model_name",
            response_data={"error": "Bad request: [('string_too_short', ('body', 'model_id'))]"},
        )
        model_id, model_client, model_input = stub
        with self.assertRaises(WcaInvalidModelId) as e:
            model_client.codematch(model_input=model_input, model_id=model_id)
        self.assertEqual(e.exception.model_id, model_id)

    @assert_call_count_metrics(metric=wca_codematch_hist)
    def test_codematch_invalid_model_id_for_api_key(self):
        stub = stub_wca_client(403, "sample_model_name")
        model_id, model_client, model_input = stub
        with self.assertRaises(WcaInvalidModelId) as e:
            model_client.codematch(model_input=model_input, model_id=model_id)
        self.assertEqual(e.exception.model_id, model_id)

    @assert_call_count_metrics(metric=wca_codematch_hist)
    def test_codematch_empty_response(self):
        stub = stub_wca_client(204, "sample_model_name")
        model_id, model_client, model_input = stub
        with self.assertRaises(WcaEmptyResponse) as e:
            model_client.codematch(model_input=model_input, model_id=model_id)
        self.assertEqual(e.exception.model_id, model_id)


@override_settings(ANSIBLE_AI_MODEL_MESH_MODEL_NAME=None)
class TestDummySecretManager(TestCase):
    def setUp(self):
        super().setUp()
        self.now_patcher = patch.object(django.utils.timezone, 'now', return_value=datetime.now())
        self.mocked_now = self.now_patcher.start()

    def tearDown(self):
        self.now_patcher.stop()
        super().tearDown()

    def test_load_secrets(self):
        expectation = {
            123123: {
                Suffixes.API_KEY: DummySecretEntry.from_string("some-key"),
                Suffixes.MODEL_ID: DummySecretEntry.from_string("valid"),
            },
            23421344: {
                Suffixes.API_KEY: DummySecretEntry.from_string("some-key"),
                Suffixes.MODEL_ID: DummySecretEntry.from_string("whatever"),
            },
        }
        got = DummySecretManager.load_secrets("123123:valid,23421344:whatever")
        self.assertEqual(got, expectation)

    @override_settings(WCA_SECRET_DUMMY_SECRETS='123:abcdef<sep>sec,12353:efreg<sep>sec')
    def test_get_secret(self):
        sm = DummySecretManager()
        self.assertEqual(sm.get_secret(123, Suffixes.API_KEY)["SecretString"], "abcdef")


@override_settings(WCA_SECRET_BACKEND_TYPE="dummy")
@override_settings(ANSIBLE_AI_MODEL_MESH_MODEL_NAME=None)
@override_settings(WCA_SECRET_DUMMY_SECRETS="")
class TestWCAClientOnPrem(WisdomAppsBackendMocking, WisdomServiceLogAwareTestCase):
    @override_settings(ANSIBLE_WCA_USERNAME='username')
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_KEY='12345')
    def test_get_api_key(self):
        model_client = WCAOnPremClient(inference_url='http://example.com/')
        api_key = model_client.get_api_key(11009103)
        self.assertEqual(api_key, '12345')

    @override_settings(ANSIBLE_WCA_USERNAME='username')
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_KEY=None)
    def test_get_api_key_without_setting(self):
        model_client = WCAClient(inference_url='http://example.com/')
        with self.assertRaises(WcaKeyNotFound):
            model_client.get_api_key(11009103)

    @override_settings(ANSIBLE_WCA_USERNAME='username')
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_KEY='12345')
    @override_settings(ANSIBLE_AI_MODEL_MESH_MODEL_NAME='model-name')
    def test_get_model_id(self):
        model_client = WCAOnPremClient(inference_url='http://example.com/')
        model_id = model_client.get_model_id(11009103)
        self.assertEqual(model_id, 'model-name')

    @override_settings(ANSIBLE_WCA_USERNAME='username')
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_KEY='12345')
    @override_settings(ANSIBLE_AI_MODEL_MESH_MODEL_NAME='model-name')
    def test_get_model_id_with_override(self):
        model_client = WCAOnPremClient(inference_url='http://example.com/')
        model_id = model_client.get_model_id(11009103, 'override-model-name')
        self.assertEqual(model_id, 'override-model-name')

    @override_settings(ANSIBLE_WCA_USERNAME='username')
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_KEY='12345')
    @override_settings(ANSIBLE_AI_MODEL_MESH_MODEL_NAME=None)
    def test_get_model_id_without_setting(self):
        model_client = WCAOnPremClient(inference_url='http://example.com/')
        with self.assertRaises(WcaModelIdNotFound):
            model_client.get_model_id(11009103)


@override_settings(ANSIBLE_WCA_RETRY_COUNT=1)
@override_settings(ANSIBLE_WCA_USERNAME='username')
@override_settings(ANSIBLE_AI_MODEL_MESH_API_KEY='12345')
@override_settings(ANSIBLE_AI_MODEL_MESH_MODEL_NAME='model-name')
@override_settings(ANSIBLE_AI_MODEL_MESH_API_TIMEOUT=None)
class TestWCAOnPremCodegen(WisdomServiceLogAwareTestCase):
    def test_headers(self):
        suggestion_id = 'suggestion_id'
        prompt = "- name: install ffmpeg on Red Hat Enterprise Linux"
        token = base64.b64encode(bytes('username:12345', 'ascii')).decode("ascii")

        model_input = {
            "instances": [
                {
                    "context": "",
                    "prompt": prompt,
                }
            ]
        }
        codegen_data = {
            "model_id": 'model-name',
            "prompt": f"{prompt}\n",
        }

        request_headers = {
            "Authorization": f"ZenApiKey {token}",
            WCA_REQUEST_ID_HEADER: suggestion_id,
        }

        model_client = WCAOnPremClient(inference_url='https://example.com')
        model_client.session.post = Mock(return_value=MockResponse(json={}, status_code=200))

        model_client.infer(
            model_input=model_input,
            suggestion_id=suggestion_id,
        )

        model_client.session.post.assert_called_once_with(
            "https://example.com/v1/wca/codegen/ansible",
            headers=request_headers,
            json=codegen_data,
            timeout=None,
        )


@override_settings(ANSIBLE_WCA_RETRY_COUNT=1)
@override_settings(ANSIBLE_WCA_USERNAME='username')
@override_settings(ANSIBLE_AI_MODEL_MESH_API_KEY='12345')
@override_settings(ANSIBLE_AI_MODEL_MESH_MODEL_NAME='model-name')
@override_settings(ANSIBLE_AI_MODEL_MESH_API_TIMEOUT=None)
class TestWCAOnPremCodematch(WisdomServiceLogAwareTestCase):
    def test_headers(self):
        suggestions = [
            "- name: install ffmpeg on Red Hat Enterprise Linux\n  "
            "ansible.builtin.package:\n    name:\n      - ffmpeg\n    state: present\n",
            "- name: This is another test",
        ]
        model_input = {"suggestions": suggestions}
        data = {
            "model_id": 'model-name',
            "input": suggestions,
        }
        token = base64.b64encode(bytes('username:12345', 'ascii')).decode("ascii")

        request_headers = {
            "Authorization": f"ZenApiKey {token}",
        }

        model_client = WCAOnPremClient(inference_url='https://example.com')
        model_client.session.post = Mock(return_value=MockResponse(json={}, status_code=200))

        model_client.codematch(model_input=model_input, model_id='model-name')

        model_client.session.post.assert_called_once_with(
            "https://example.com/v1/wca/codematch/ansible",
            headers=request_headers,
            json=data,
            timeout=None,
        )
