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
import json as JSON
import uuid
from datetime import datetime
from functools import wraps
from typing import Optional, Type, Union
from unittest.mock import ANY, Mock, patch

import django.utils.timezone
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
from ansible_ai_connect.ai.api.model_pipelines.exceptions import (
    ModelTimeoutError,
    WcaBadRequest,
    WcaCodeMatchFailure,
    WcaEmptyResponse,
    WcaInferenceFailure,
    WcaInvalidModelId,
    WcaKeyNotFound,
    WcaModelIdNotFound,
    WcaNoDefaultModelId,
    WcaRequestIdCorrelationFailure,
    WcaTokenFailure,
    WcaValidationFailure,
)
from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    CompletionsParameters,
    ContentMatchParameters,
    PlaybookExplanationParameters,
    PlaybookGenerationParameters,
    RoleExplanationParameters,
    RoleGenerationParameters,
)
from ansible_ai_connect.ai.api.model_pipelines.tests import mock_pipeline_config
from ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_base import (
    WCA_REQUEST_ID_HEADER,
    WCA_REQUEST_USER_UUID_HEADER,
    ibm_cloud_identity_token_hist,
    ibm_cloud_identity_token_retry_counter,
    wca_codegen_hist,
    wca_codegen_playbook_hist,
    wca_codegen_playbook_retry_counter,
    wca_codegen_retry_counter,
    wca_codegen_role_hist,
    wca_codematch_hist,
    wca_codematch_retry_counter,
    wca_explain_playbook_hist,
    wca_explain_playbook_retry_counter,
)
from ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_onprem import (
    WCAOnPremCompletionsPipeline,
    WCAOnPremContentMatchPipeline,
)
from ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_saas import (
    WCASaaSCompletionsPipeline,
    WCASaaSContentMatchPipeline,
    WCASaaSPlaybookExplanationPipeline,
    WCASaaSPlaybookGenerationPipeline,
    WCASaaSRoleExplanationPipeline,
    WCASaaSRoleGenerationPipeline,
)
from ansible_ai_connect.test_utils import (
    WisdomAppsBackendMocking,
    WisdomServiceAPITestCaseBaseOIDC,
    WisdomServiceLogAwareTestCase,
)
from ansible_ai_connect.users.models import Plan

DEFAULT_REQUEST_ID = str(uuid.uuid4())


class MockResponse:
    def __init__(self, json, status_code, headers=None, text=None):
        self._json = json
        self.status_code = status_code
        self.headers = {} if headers is None else headers
        self.text = JSON.dumps(json) if text is None else text
        self.content = JSON.dumps(json).encode("utf-8")

    def json(self):
        return self._json

    def raise_for_status(self):
        return


def stub_wca_client(
    status_code,
    model_id,
    prompt="- name: install ffmpeg on Red Hat Enterprise Linux",
    response_data: dict = None,
    pipeline: Union[
        Type[WCASaaSCompletionsPipeline], Type[WCASaaSContentMatchPipeline]
    ] = WCASaaSCompletionsPipeline,
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
        headers={WCA_REQUEST_ID_HEADER: str(DEFAULT_REQUEST_ID)},
    )
    model_client = pipeline(mock_pipeline_config("wca"))
    model_client.session.post = Mock(return_value=response)
    model_client.get_api_key = Mock(return_value="org-api-key")
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


@override_settings(WCA_SECRET_BACKEND_TYPE="dummy")
class TestWCAClient(WisdomAppsBackendMocking, WisdomServiceAPITestCaseBaseOIDC):
    def setUp(self):
        super().setUp()

        # Create mock configuration
        self.config = mock_pipeline_config("wca")
        self.config.api_key = None
        self.config.model_id = None
        self.model_client = WCASaaSCompletionsPipeline(self.config)

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1981:my-key<sep>my-optimized-model")
    def test_mock_wca_get_api_key(self):
        api_key = self.model_client.get_api_key(self.user)
        self.assertEqual(api_key, "my-key")

    def test_get_api_key_without_org_id(self):
        with self.assertRaises(WcaKeyNotFound):
            self.model_client.get_api_key(self.user)

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1981:12345<sep>my-model")
    def test_get_api_key_from_aws(self):
        secret_value = "12345"
        api_key = self.model_client.get_api_key(self.user)
        self.assertEqual(api_key, secret_value)

    def test_get_api_key_from_aws_error(self):
        m = Mock()
        m.get_secret.side_effect = WcaSecretManagerError
        self.mock_wca_secret_manager_with(m)
        with self.assertRaises(WcaSecretManagerError):
            self.model_client.get_api_key(self.user)

    def test_get_api_key_with_environment_override(self):
        self.config.api_key = "key"
        api_key = self.model_client.get_api_key(self.user)
        self.assertEqual(api_key, "key")

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1981:my-key<sep>my-great-model")
    def test_get_model_id_with_empty_model(self):
        model_id = self.model_client.get_model_id(self.user, requested_model_id="")
        self.assertEqual(model_id, "my-great-model")

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1981:my-key<sep>org-model")
    def test_get_model_id_get_org_default_model(self):
        model_id = self.model_client.get_model_id(self.user, None)
        self.assertEqual(model_id, "org-model")

    def test_get_model_id_with_model_override(self):
        model_id = self.model_client.get_model_id(self.user, "model-i-pick")
        self.assertEqual(model_id, "model-i-pick")

    def test_get_model_id_without_org_id(self):
        self.user.organization = None
        with self.assertRaises(WcaNoDefaultModelId):
            self.model_client.get_model_id(self.user, None)

    @override_settings(WCA_SECRET_DUMMY_SECRETS="1981:")
    def test_get_api_key_org_cannot_have_no_key(self):
        with self.assertRaises(WcaKeyNotFound):
            self.model_client.get_api_key(self.user)

    @override_settings(WCA_SECRET_DUMMY_SECRETS="")
    def test_get_model_id_org_cannot_have_no_model(self):
        with self.assertRaises(WcaModelIdNotFound):
            self.model_client.get_model_id(self.user, None)

    def test_model_id_with_override(self):
        self.config.model_id = "gemini"
        model_id = self.model_client.get_model_id(self.user, None)
        self.assertEqual(model_id, "gemini")

    def test_model_id_with_environment_and_user_override(self):
        self.config.model_id = "gemini"
        model_id = self.model_client.get_model_id(self.user, "bard")
        self.assertEqual(model_id, "bard")


@override_settings(ANSIBLE_AI_ENABLE_ONE_CLICK_TRIAL=True)
@override_settings(WCA_SECRET_BACKEND_TYPE="dummy")
class TestWCAClientWithTrial(WisdomServiceAPITestCaseBaseOIDC, WisdomServiceLogAwareTestCase):
    def setUp(self):
        super().setUp()
        config = mock_pipeline_config(
            "wca",
            api_key=None,
            model_id=None,
            one_click_default_model_id="fancy-model",
            one_click_default_api_key="and-my-key",
        )
        self.config = config
        self.model_client = WCASaaSCompletionsPipeline(self.config)

        trial_plan, _ = Plan.objects.get_or_create(name="trial of 90 days", expires_after="90 days")
        self.user.plans.add(trial_plan)

    def test_get_model_id_with_active_trial(self):
        model_id = self.model_client.get_model_id(self.user, "override-model-name")
        self.assertEqual(model_id, "fancy-model")

    def test_get_api_key_with_active_trial(self):
        api_key = self.model_client.get_api_key(self.user)
        self.assertEqual(api_key, "and-my-key")

    def test_get_model_id_with_expired_trial(self):
        up = self.user.userplan_set.first()
        up.expired_at = up.created_at
        up.save()
        model_id = self.model_client.get_model_id(self.user, "override-model-name")
        self.assertNotEqual(model_id, "fancy-model")

    def test_get_api_key_with_expired_trial(self):
        up = self.user.userplan_set.first()
        up.expired_at = up.created_at
        up.save()
        api_key = ""
        try:
            api_key = self.model_client.get_api_key(self.user)
        except WcaKeyNotFound:
            pass
        self.assertNotEqual(api_key, "and-my-key")

    @override_settings(
        WCA_SECRET_DUMMY_SECRETS="1981:org_key<sep>org_model_id<|sepofid|>org_model_name"
    )
    def test_get_api_key_with_wca_configured(self):
        api_key = self.model_client.get_api_key(self.user)
        model_id = self.model_client.get_model_id(self.user)
        self.assertEqual(api_key, "org_key")
        self.assertEqual(model_id, "org_model_id<|sepofid|>org_model_name")


@override_settings(WCA_SECRET_BACKEND_TYPE="dummy")
@override_settings(ENABLE_ANSIBLE_LINT_POSTPROCESS=False)
class TestWCAClientPlaybookGeneration(WisdomAppsBackendMocking, WisdomServiceLogAwareTestCase):
    def setUp(self):
        super().setUp()
        wca_client = WCASaaSPlaybookGenerationPipeline(
            mock_pipeline_config("wca", api_key=None, model_id=None)
        )
        wca_client.get_api_key = Mock(return_value="some-key")
        wca_client.get_token = Mock(return_value={"access_token": "a-token"})
        wca_client.get_model_id = Mock(return_value="a-random-model")
        wca_client.session = Mock()
        response = Mock
        response.text = '{"playbook": "Oh!", "outline": "Ahh!", "explanation": "!Óh¡"}'
        response.status_code = 200
        response.headers = {WCA_REQUEST_ID_HEADER: WCA_REQUEST_ID_HEADER}
        response.raise_for_status = Mock()
        wca_client.session.post.return_value = response
        self.wca_client = wca_client

    @assert_call_count_metrics(metric=wca_codegen_playbook_hist)
    def test_playbook_gen(self):
        request = Mock()
        playbook, outline, warnings = self.wca_client.invoke(
            PlaybookGenerationParameters.init(
                request=request, text="Install Wordpress", create_outline=True
            )
        )
        self.assertEqual(playbook, "Oh!")
        self.assertEqual(outline, "Ahh!")

    @assert_call_count_metrics(metric=wca_codegen_playbook_hist)
    def test_playbook_gen_custom_prompt(self):
        request = Mock()
        self.wca_client.invoke(
            PlaybookGenerationParameters.init(
                request=request,
                text="Install Wordpress",
                custom_prompt="You are an Ansible expert",
                create_outline=True,
            )
        )
        self.wca_client.session.post.assert_called_once_with(
            "http://localhost/v1/wca/codegen/ansible/playbook",
            headers=ANY,
            json={
                "model_id": "a-random-model",
                "text": "Install Wordpress",
                "create_outline": True,
                "custom_prompt": "You are an Ansible expert\n",
            },
        )

    @assert_call_count_metrics(metric=wca_codegen_playbook_hist)
    def test_playbook_gen_custom_prompt_with_trailing_newline(self):
        request = Mock()
        self.wca_client.invoke(
            PlaybookGenerationParameters.init(
                request=request,
                text="Install Wordpress",
                custom_prompt="You are an Ansible expert\n",
                create_outline=True,
            )
        )
        self.wca_client.session.post.assert_called_once_with(
            "http://localhost/v1/wca/codegen/ansible/playbook",
            headers=ANY,
            json={
                "model_id": "a-random-model",
                "text": "Install Wordpress",
                "create_outline": True,
                "custom_prompt": "You are an Ansible expert\n",
            },
        )

    @assert_call_count_metrics(metric=wca_codegen_playbook_hist)
    @assert_call_count_metrics(metric=wca_codegen_playbook_retry_counter)
    def test_playbook_gen_error(self):
        request = Mock()
        model_client = WCASaaSPlaybookGenerationPipeline(mock_pipeline_config("wca"))
        model_client.get_api_key = Mock(return_value="some-key")
        model_client.get_token = Mock(return_value={"access_token": "a-token"})
        model_client.get_model_id = Mock(return_value="a-random-model")
        model_client.session = Mock()
        model_client.session.post = Mock(side_effect=HTTPError(500))
        with (
            self.assertRaises(HTTPError),
            self.assertLogs(
                logger="ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_base", level="INFO"
            ) as log,
        ):
            model_client.invoke(
                PlaybookGenerationParameters.init(
                    request=request, text="Install Wordpress", create_outline=True
                )
            )
            self.assertInLog("Caught retryable error after 1 tries.", log)

    def test_playbook_gen_model_id(self):
        self.assertion_count = 0
        request = Mock()
        model_client = WCASaaSPlaybookGenerationPipeline(mock_pipeline_config("wca"))
        model_client.get_api_key = Mock(return_value="some-key")
        model_client.get_token = Mock(return_value={"access_token": "a-token"})
        model_client.session = Mock()

        def get_my_model_id(user, model_id):
            self.assertEqual(model_id, "mymodel")
            self.assertion_count += 1
            return model_id

        model_client.get_model_id = get_my_model_id

        model_client.invoke(
            PlaybookGenerationParameters.init(
                request=request, text="Install Wordpress", create_outline=True, model_id="mymodel"
            )
        )
        self.assertGreater(self.assertion_count, 0)

    @assert_call_count_metrics(metric=wca_codegen_playbook_hist)
    def test_playbook_gen_no_org(self):
        request = Mock()
        request.user.organization = None
        self.wca_client.invoke(
            PlaybookGenerationParameters.init(request=request, text="Install Wordpress")
        )
        self.wca_client.get_api_key.assert_called_with(request.user)

    @assert_call_count_metrics(metric=wca_codegen_playbook_hist)
    @override_settings(ENABLE_ANSIBLE_LINT_POSTPROCESS=True)
    def test_playbook_gen_with_lint(self):
        fake_linter = Mock()
        fake_linter.run_linter.return_value = "I'm super fake!"
        self.mock_ansible_lint_caller_with(fake_linter)
        playbook, outline, warnings = self.wca_client.invoke(
            PlaybookGenerationParameters.init(
                request=Mock(), text="Install Wordpress", create_outline=True
            )
        )
        self.assertEqual(playbook, "I'm super fake!")
        self.assertEqual(outline, "Ahh!")

    @assert_call_count_metrics(metric=wca_codegen_playbook_hist)
    @override_settings(ENABLE_ANSIBLE_LINT_POSTPROCESS=True)
    def test_playbook_gen_when_is_not_initialized(self):
        self.mock_ansible_lint_caller_with(None)
        playbook, outline, warnings = self.wca_client.invoke(
            PlaybookGenerationParameters.init(
                request=Mock(), text="Install Wordpress", create_outline=True
            )
        )
        # Ensure nothing was done
        self.assertEqual(playbook, "Oh!")

    def test_playbook_gen_request_id_correlation_failure(self):
        request = Mock()
        request.user.organization = None

        self.wca_client.session.post.return_value = MockResponse(
            json={},
            status_code=200,
            headers={WCA_REQUEST_ID_HEADER: "some-other-uuid"},
        )
        with self.assertRaises(WcaRequestIdCorrelationFailure):
            self.wca_client.invoke(
                PlaybookGenerationParameters.init(
                    request=Mock(),
                    text="Install Wordpress",
                    create_outline=True,
                    generation_id=str(DEFAULT_REQUEST_ID),
                )
            )


@override_settings(WCA_SECRET_BACKEND_TYPE="dummy")
@override_settings(ENABLE_ANSIBLE_LINT_POSTPROCESS=False)
class TestWCAClientRoleGeneration(WisdomAppsBackendMocking, WisdomServiceLogAwareTestCase):
    def setUp(self):
        super().setUp()
        wca_client = WCASaaSRoleGenerationPipeline(
            mock_pipeline_config("wca", api_key=None, model_id=None)
        )
        wca_client.get_api_key = Mock(return_value="some-key")
        wca_client.get_token = Mock(return_value={"access_token": "a-token"})
        wca_client.get_model_id = Mock(return_value="a-random-model")
        wca_client.session = Mock()
        response = Mock
        response.text = (
            '{"name": "foo_bar", "outline": "Ahh!", "files": [{"path": '
            '"roles/foo_bar/tasks/main.yml", "content": "- package:\\n    name: emacs", '
            '"file_type": "task"}, {"path": "roles/foo_bar/defaults/main.yml", '
            '"content": "my_var: some content", "file_type": "default"}], "warnings": []}'
        )
        response.status_code = 200
        response.headers = {WCA_REQUEST_ID_HEADER: WCA_REQUEST_ID_HEADER}
        response.raise_for_status = Mock()
        wca_client.session.post.return_value = response
        self.wca_client = wca_client
        self.mock_ansible_lint_caller_with(None)

    @assert_call_count_metrics(metric=wca_codegen_role_hist)
    @override_settings(ENABLE_ANSIBLE_LINT_POSTPROCESS=True)
    def test_role_gen_with_lint_mocked(self):
        fake_linter = Mock()
        fake_linter.run_linter.return_value = "I'm super fake!"
        self.mock_ansible_lint_caller_with(fake_linter)
        name, files, outline, warnings = self.wca_client.invoke(
            RoleGenerationParameters.init(
                request=Mock(), text="Install Wordpress", create_outline=True
            )
        )
        self.assertEqual(name, "foo_bar")
        self.assertEqual(outline, "Ahh!")
        self.assertEqual(warnings, [])
        for file in files:
            if file["file_type"] != "task":
                continue
            self.assertEqual(file["content"], "I'm super fake!")

    @assert_call_count_metrics(metric=wca_codegen_role_hist)
    @override_settings(ENABLE_ANSIBLE_LINT_POSTPROCESS=False)
    def test_role_gen_when_is_off(self):
        name, files, outline, warnings = self.wca_client.invoke(
            RoleGenerationParameters.init(
                request=Mock(), text="Install Wordpress", create_outline=True
            )
        )
        self.assertEqual(name, "foo_bar")
        self.assertEqual(outline, "Ahh!")
        self.assertEqual(warnings, [])
        for file in files:
            if file["file_type"] != "task":
                continue
            self.assertEqual(file["content"], "- package:\n    name: emacs")

    @assert_call_count_metrics(metric=wca_codegen_role_hist)
    @override_settings(ENABLE_ANSIBLE_LINT_POSTPROCESS=True)
    def test_role_gen_when_is_on(self):
        name, files, outline, warnings = self.wca_client.invoke(
            RoleGenerationParameters.init(
                request=Mock(), text="Install Wordpress", create_outline=True
            )
        )
        self.assertEqual(name, "foo_bar")
        self.assertEqual(outline, "Ahh!")
        self.assertEqual(warnings, [])
        for file in files:
            if file["file_type"] != "task":
                continue
            self.assertEqual(file["content"], "---\n- ansible.builtin.package:\n    name: emacs\n")


@override_settings(WCA_SECRET_BACKEND_TYPE="dummy")
@override_settings(ENABLE_ANSIBLE_LINT_POSTPROCESS=False)
class TestWCAClientExplanation(WisdomAppsBackendMocking, WisdomServiceLogAwareTestCase):
    def setUp(self):
        super().setUp()
        wca_client = WCASaaSPlaybookExplanationPipeline(
            mock_pipeline_config("wca", api_key=None, model_id=None)
        )
        wca_client.get_api_key = Mock(return_value="some-key")
        wca_client.get_token = Mock(return_value={"access_token": "a-token"})
        wca_client.get_model_id = Mock(return_value="a-random-model")
        wca_client.session = Mock()
        response = Mock
        response.text = '{"playbook": "Oh!", "outline": "Ahh!", "explanation": "!Óh¡"}'
        response.status_code = 200
        response.headers = {WCA_REQUEST_ID_HEADER: WCA_REQUEST_ID_HEADER}
        response.raise_for_status = Mock()
        wca_client.session.post.return_value = response
        self.wca_client = wca_client

    @assert_call_count_metrics(metric=wca_explain_playbook_hist)
    def test_playbook_exp(self):
        request = Mock()
        explanation = self.wca_client.invoke(
            PlaybookExplanationParameters.init(request=request, content="Some playbook")
        )
        self.assertEqual(explanation, "!Óh¡")

    @assert_call_count_metrics(metric=wca_explain_playbook_hist)
    def test_playbook_exp_custom_prompt(self):
        request = Mock()
        self.wca_client.invoke(
            PlaybookExplanationParameters.init(
                request=request, content="Some playbook", custom_prompt="Explain this"
            )
        )
        self.wca_client.session.post.assert_called_once_with(
            "http://localhost/v1/wca/explain/ansible/playbook",
            headers=ANY,
            json={
                "model_id": "a-random-model",
                "playbook": "Some playbook",
                "custom_prompt": "Explain this\n",
            },
        )

    @assert_call_count_metrics(metric=wca_explain_playbook_hist)
    def test_playbook_exp_custom_prompt_with_trailing_newline(self):
        request = Mock()
        self.wca_client.invoke(
            PlaybookExplanationParameters.init(
                request=request, content="Some playbook", custom_prompt="Explain this\n"
            )
        )
        self.wca_client.session.post.assert_called_once_with(
            "http://localhost/v1/wca/explain/ansible/playbook",
            headers=ANY,
            json={
                "model_id": "a-random-model",
                "playbook": "Some playbook",
                "custom_prompt": "Explain this\n",
            },
        )

    @assert_call_count_metrics(metric=wca_explain_playbook_hist)
    @assert_call_count_metrics(metric=wca_explain_playbook_retry_counter)
    def test_playbook_exp_error(self):
        request = Mock()
        model_client = WCASaaSPlaybookExplanationPipeline(mock_pipeline_config("wca"))
        model_client.get_api_key = Mock(return_value="some-key")
        model_client.get_token = Mock(return_value={"access_token": "a-token"})
        model_client.get_model_id = Mock(return_value="a-random-model")
        model_client.session = Mock()
        model_client.session.post = Mock(side_effect=HTTPError(500))
        with (
            self.assertRaises(HTTPError),
            self.assertLogs(
                logger="ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_base", level="INFO"
            ) as log,
        ):
            model_client.invoke(
                PlaybookExplanationParameters.init(request=request, content="Some playbook")
            )
            self.assertInLog("Caught retryable error after 1 tries.", log)

    def test_playbook_exp_model_id(self):
        request = Mock()
        model_client = WCASaaSPlaybookExplanationPipeline(mock_pipeline_config("wca"))
        model_client.get_api_key = Mock(return_value="some-key")
        model_client.get_token = Mock(return_value={"access_token": "a-token"})
        model_client.session = Mock()

        self.assertion_count = 0

        def get_my_model_id(user, model_id):
            self.assertEqual(model_id, "mymodel")
            self.assertion_count += 1
            return model_id

        model_client.get_model_id = get_my_model_id

        model_client.invoke(
            PlaybookExplanationParameters.init(
                request=request, content="Some playbook", model_id="mymodel"
            )
        )
        self.assertGreater(self.assertion_count, 0)
        self.assertion_count = 0

    @assert_call_count_metrics(metric=wca_explain_playbook_hist)
    def test_playbook_gen_no_org(self):
        request = Mock()
        request.user.organization = None
        self.wca_client.invoke(
            PlaybookExplanationParameters.init(request=request, content="Install Wordpress")
        )
        self.wca_client.get_api_key.assert_called_with(request.user)

    @assert_call_count_metrics(metric=wca_explain_playbook_hist)
    def test_playbook_exp_no_org(self):
        request = Mock()
        request.user.organization = None
        self.wca_client.invoke(
            PlaybookExplanationParameters.init(request=request, content="Some playbook")
        )
        self.wca_client.get_api_key.assert_called_with(request.user)

    def test_playbook_exp_request_id_correlation_failure(self):
        request = Mock()
        request.user.organization = None

        self.wca_client.session.post.return_value = MockResponse(
            json={},
            status_code=200,
            headers={WCA_REQUEST_ID_HEADER: "some-other-uuid"},
        )
        with self.assertRaises(WcaRequestIdCorrelationFailure):
            self.wca_client.invoke(
                PlaybookExplanationParameters.init(
                    request=request, content="Some playbook", explanation_id=str(DEFAULT_REQUEST_ID)
                )
            )


@override_settings(WCA_SECRET_BACKEND_TYPE="dummy")
class TestWCACodegen(WisdomAppsBackendMocking, WisdomServiceLogAwareTestCase):

    def setUp(self):
        super().setUp()
        config = mock_pipeline_config(
            "wca",
            retry_count=1,
            timeout=None,
            idp_url="https://iam.cloud.ibm.com/identity",
            idp_login=None,
            idp_password=None,
            verify_ssl=True,
        )
        self.config = config

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

        model_client = WCASaaSCompletionsPipeline(self.config)
        model_client.session.post = Mock(return_value=response)
        model_client.get_token("abcdef")

        model_client.session.post.assert_called_once_with(
            "https://iam.cloud.ibm.com/identity/token",
            headers=headers,
            data=data,
            auth=None,
        )

    @assert_call_count_metrics(metric=ibm_cloud_identity_token_hist)
    def test_get_token_with_auth(self):
        self.config.idp_url = "http://some-different-idp"
        self.config.idp_login = "jimmy"
        self.config.idp_password = "jimmy"
        model_client = WCASaaSCompletionsPipeline(self.config)
        model_client.session.post = Mock()
        basic = HTTPBasicAuth("jimmy", "jimmy")

        model_client.get_token("abcdef")

        model_client.session.post.assert_called_once_with(
            "http://some-different-idp/token",
            headers=ANY,
            data=ANY,
            auth=basic,
        )

    @assert_call_count_metrics(metric=ibm_cloud_identity_token_hist)
    @assert_call_count_metrics(metric=ibm_cloud_identity_token_retry_counter)
    def test_get_token_http_error(self):
        model_client = WCASaaSCompletionsPipeline(self.config)
        model_client.session.post = Mock(side_effect=HTTPError(404))
        with (
            self.assertRaises(WcaTokenFailure),
            self.assertLogs(
                logger="ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_base", level="INFO"
            ) as log,
        ):
            model_client.get_token("api-key")
            self.assertInLog("Caught retryable error after 1 tries.", log)

    @assert_call_count_metrics(metric=wca_codegen_hist)
    def test_infer(self):
        self._do_inference(
            suggestion_id=str(DEFAULT_REQUEST_ID), request_id=str(DEFAULT_REQUEST_ID)
        )

    @assert_call_count_metrics(metric=wca_codegen_hist)
    def test_infer_organization_id_is_none(self):
        self._do_inference(
            suggestion_id=str(DEFAULT_REQUEST_ID),
            organization_id=None,
            request_id=str(DEFAULT_REQUEST_ID),
        )

    @assert_call_count_metrics(metric=wca_codegen_hist)
    def test_infer_without_suggestion_id(self):
        self._do_inference(suggestion_id=None, request_id=str(DEFAULT_REQUEST_ID))

    @assert_call_count_metrics(metric=wca_codegen_hist)
    def test_infer_without_request_id_header(self):
        self._do_inference(suggestion_id=str(DEFAULT_REQUEST_ID), request_id=None)

    def _do_inference(
        self,
        suggestion_id=None,
        organization_id: Optional[int] = 123,
        request_id=None,
        prompt=None,
        codegen_prompt=None,
    ):
        model_id = "zavala"
        api_key = "abc123"
        user_uuid = str(uuid.uuid4())
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
            headers={WCA_REQUEST_ID_HEADER: request_id, WCA_REQUEST_USER_UUID_HEADER: user_uuid},
        )

        requestHeaders = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token['access_token']}",
            WCA_REQUEST_ID_HEADER: suggestion_id,
            WCA_REQUEST_USER_UUID_HEADER: user_uuid,
        }

        model_client = WCASaaSCompletionsPipeline(self.config)
        model_client.session.post = Mock(return_value=response)
        model_client.get_token = Mock(return_value=token)
        model_client.get_model_id = Mock(return_value=model_id)
        model_client.get_api_key = Mock(return_value=api_key)

        mock_request = Mock()
        mock_request.user = Mock()
        mock_request.user.uuid = user_uuid

        result = model_client.invoke(
            CompletionsParameters.init(
                request=mock_request,
                model_input=model_input,
                model_id=model_id,
                suggestion_id=suggestion_id,
            ),
        )

        model_client.get_token.assert_called_once()
        model_client.session.post.assert_called_once_with(
            "http://localhost/v1/wca/codegen/ansible",
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
        model_client = WCASaaSCompletionsPipeline(self.config)
        model_client.get_token = Mock(return_value=token)
        model_client.session.post = Mock(side_effect=ReadTimeout())
        model_client.get_model_id = Mock(return_value=model_id)
        model_client.get_api_key = Mock(return_value=api_key)
        with self.assertRaises(ModelTimeoutError) as e:
            model_client.invoke(
                CompletionsParameters.init(
                    request=Mock(),
                    model_input=model_input,
                    model_id=model_id,
                    suggestion_id=DEFAULT_REQUEST_ID,
                ),
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
        model_client = WCASaaSCompletionsPipeline(self.config)
        model_client.get_token = Mock(return_value=token)
        model_client.session.post = Mock(side_effect=HTTPError(404))
        model_client.get_model_id = Mock(return_value=model_id)
        model_client.get_api_key = Mock(return_value=api_key)
        with (
            self.assertRaises(WcaInferenceFailure) as e,
            self.assertLogs(
                logger="ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_base", level="INFO"
            ) as log,
        ):
            model_client.invoke(
                CompletionsParameters.init(
                    request=Mock(),
                    model_input=model_input,
                    model_id=model_id,
                    suggestion_id=DEFAULT_REQUEST_ID,
                ),
            )
            self.assertInLog("Caught retryable error after 1 tries.", log)
        self.assertEqual(e.exception.model_id, model_id)

    @assert_call_count_metrics(metric=wca_codegen_hist)
    def test_infer_unrecognized_404(self):
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
        response = MockResponse(
            json={"some": "mystery 404 response"},
            status_code=404,
            headers={"Content-Type": "application/json"},
        )
        model_client = WCASaaSCompletionsPipeline(self.config)
        model_client.get_token = Mock(return_value=token)
        model_client.session.post = Mock(return_value=response)
        model_client.get_model_id = Mock(return_value=model_id)
        model_client.get_api_key = Mock(return_value=api_key)
        with self.assertRaises(WcaInferenceFailure) as e:
            with self.assertLogs(logger="root", level="ERROR") as log:
                model_client.invoke(
                    CompletionsParameters.init(
                        request=Mock(),
                        model_input=model_input,
                        model_id=model_id,
                        suggestion_id=DEFAULT_REQUEST_ID,
                    ),
                )
        self.assertEqual(e.exception.model_id, model_id)
        self.assertInLog(
            "WCA request failed with 404. Content-Type:application/json, "
            'Content:b\'{"some": "mystery 404 response"}\'',
            log,
        )

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
            headers={WCA_REQUEST_ID_HEADER: "some-other-uuid"},
        )
        model_client = WCASaaSCompletionsPipeline(self.config)
        model_client.session.post = Mock(return_value=response)
        model_client.get_token = Mock(return_value=token)
        model_client.get_model_id = Mock(return_value=model_id)
        model_client.get_api_key = Mock(return_value=api_key)

        with self.assertRaises(WcaRequestIdCorrelationFailure) as e:
            model_client.invoke(
                CompletionsParameters.init(
                    request=Mock(),
                    model_input=model_input,
                    model_id=model_id,
                    suggestion_id=DEFAULT_REQUEST_ID,
                ),
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
            model_client.invoke(
                CompletionsParameters.init(
                    request=Mock(),
                    model_input=model_input,
                    model_id=model_id,
                    suggestion_id=DEFAULT_REQUEST_ID,
                ),
            )
        self.assertEqual(e.exception.model_id, model_id)

    @assert_call_count_metrics(metric=wca_codegen_hist)
    def test_infer_invalid_model_id_for_api_key(self):
        stub = stub_wca_client(403, "zavala")
        model_id, model_client, model_input = stub
        with self.assertRaises(WcaInvalidModelId) as e:
            model_client.invoke(
                CompletionsParameters.init(
                    request=Mock(),
                    model_input=model_input,
                    model_id=model_id,
                    suggestion_id=DEFAULT_REQUEST_ID,
                ),
            )
        self.assertEqual(e.exception.model_id, model_id)

    @assert_call_count_metrics(metric=wca_codegen_hist)
    def test_infer_empty_response(self):
        stub = stub_wca_client(204, "zavala")
        model_id, model_client, model_input = stub
        with self.assertRaises(WcaEmptyResponse) as e:
            model_client.invoke(
                CompletionsParameters.init(
                    request=Mock(),
                    model_input=model_input,
                    model_id=model_id,
                    suggestion_id=DEFAULT_REQUEST_ID,
                ),
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
            model_client.invoke(
                CompletionsParameters.init(
                    request=Mock(),
                    model_input=model_input,
                    model_id=model_id,
                    suggestion_id=DEFAULT_REQUEST_ID,
                ),
            )

    @assert_call_count_metrics(metric=wca_codegen_hist)
    def test_infer_wca_validation_failure(self):
        model_id = "zavala"
        api_key = "abc123"
        model_input = {
            "instances": [
                {
                    "context": "null",
                    "prompt": "- name: delete virtual server with rate limit 50",
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
        response = MockResponse(
            json={"detail": "Validation failed"},
            status_code=422,
            headers={"Content-Type": "application/json"},
        )
        model_client = WCASaaSCompletionsPipeline(self.config)
        model_client.get_token = Mock(return_value=token)
        model_client.session.post = Mock(return_value=response)
        model_client.get_model_id = Mock(return_value=model_id)
        model_client.get_api_key = Mock(return_value=api_key)
        with self.assertRaises(WcaValidationFailure) as e:
            with self.assertLogs(logger="root", level="ERROR") as log:
                model_client.invoke(
                    CompletionsParameters.init(
                        request=Mock(),
                        model_input=model_input,
                        model_id=model_id,
                        suggestion_id=DEFAULT_REQUEST_ID,
                    ),
                )
        self.assertEqual(e.exception.model_id, model_id)
        self.assertInLog(
            "WCA request failed with 422. Content-Type:application/json, "
            'Content:b\'{"detail": "Validation failed"}\'',
            log,
        )

    @assert_call_count_metrics(metric=wca_codegen_hist)
    def test_infer_multitask_with_task_preamble(self):
        self._do_inference(
            suggestion_id=str(DEFAULT_REQUEST_ID),
            request_id=str(DEFAULT_REQUEST_ID),
            prompt="# - name: install ffmpeg on Red Hat Enterprise Linux",
            codegen_prompt="# install ffmpeg on red hat enterprise linux\n",
        )


class TestWCACodematch(WisdomServiceLogAwareTestCase):
    def setUp(self):
        super().setUp()
        self.now_patcher = patch.object(django.utils.timezone, "now", return_value=datetime.now())
        self.mocked_now = self.now_patcher.start()
        config = mock_pipeline_config("wca", timeout=None, verify_ssl=True)
        self.config = config

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

        model_client = WCASaaSContentMatchPipeline(self.config)
        model_client.session.post = Mock(return_value=response)
        model_client.get_token = Mock(return_value=token)
        model_client.get_model_id = Mock(return_value=model_id)
        model_client.get_api_key = Mock(return_value=api_key)

        result = model_client.invoke(
            ContentMatchParameters.init(request=Mock(), model_input=model_input, model_id=model_id)
        )

        model_client.get_token.assert_called_once()
        model_client.session.post.assert_called_once_with(
            "http://localhost/v1/wca/codematch/ansible",
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
        model_client = WCASaaSContentMatchPipeline(self.config)
        model_client.get_token = Mock(return_value=token)
        model_client.session.post = Mock(side_effect=ReadTimeout())
        model_client.get_model_id = Mock(return_value=model_id)
        model_client.get_api_key = Mock(return_value=api_key)
        with self.assertRaises(ModelTimeoutError) as e:
            model_client.invoke(
                ContentMatchParameters.init(
                    request=Mock(), model_input=model_input, model_id=model_id
                )
            )
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
        model_client = WCASaaSContentMatchPipeline(self.config)
        model_client.get_token = Mock(return_value=token)
        model_client.session.post = Mock(side_effect=HTTPError(404))
        model_client.get_model_id = Mock(return_value=model_id)
        model_client.get_api_key = Mock(return_value=api_key)
        with (
            self.assertRaises(WcaCodeMatchFailure) as e,
            self.assertLogs(
                logger="ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_base", level="INFO"
            ) as log,
        ):
            model_client.invoke(
                ContentMatchParameters.init(
                    request=Mock(), model_input=model_input, model_id=model_id
                )
            )
            self.assertInLog("Caught retryable error after 1 tries.", log)
        self.assertEqual(e.exception.model_id, model_id)

    @assert_call_count_metrics(metric=wca_codematch_hist)
    def test_codematch_bad_model_id(self):
        stub = stub_wca_client(
            400,
            "sample_model_name",
            response_data={"error": "Bad request: [('string_too_short', ('body', 'model_id'))]"},
            pipeline=WCASaaSContentMatchPipeline,
        )
        model_id, model_client, model_input = stub
        with self.assertRaises(WcaInvalidModelId) as e:
            model_client.invoke(
                ContentMatchParameters.init(
                    request=Mock(), model_input=model_input, model_id=model_id
                )
            )
        self.assertEqual(e.exception.model_id, model_id)

    @assert_call_count_metrics(metric=wca_codematch_hist)
    def test_codematch_invalid_model_id_for_api_key(self):
        stub = stub_wca_client(403, "sample_model_name", pipeline=WCASaaSContentMatchPipeline)
        model_id, model_client, model_input = stub
        with self.assertRaises(WcaInvalidModelId) as e:
            model_client.invoke(
                ContentMatchParameters.init(
                    request=Mock(), model_input=model_input, model_id=model_id
                )
            )
        self.assertEqual(e.exception.model_id, model_id)

    @assert_call_count_metrics(metric=wca_codematch_hist)
    def test_codematch_empty_response(self):
        stub = stub_wca_client(204, "sample_model_name", pipeline=WCASaaSContentMatchPipeline)
        model_id, model_client, model_input = stub
        with self.assertRaises(WcaEmptyResponse) as e:
            model_client.invoke(
                ContentMatchParameters.init(
                    request=Mock(), model_input=model_input, model_id=model_id
                )
            )
        self.assertEqual(e.exception.model_id, model_id)


class TestDummySecretManager(TestCase):
    def setUp(self):
        super().setUp()
        self.now_patcher = patch.object(django.utils.timezone, "now", return_value=datetime.now())
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

    @override_settings(WCA_SECRET_DUMMY_SECRETS="123:abcdef<sep>sec,12353:efreg<sep>sec")
    def test_get_secret(self):
        sm = DummySecretManager()
        self.assertEqual(sm.get_secret(123, Suffixes.API_KEY)["SecretString"], "abcdef")


@override_settings(WCA_SECRET_BACKEND_TYPE="dummy")
@override_settings(WCA_SECRET_DUMMY_SECRETS="")
class TestWCAClientOnPrem(WisdomAppsBackendMocking, WisdomServiceLogAwareTestCase):
    def setUp(self):
        super().setUp()
        self.user = Mock()
        self.user.organization.id = 11009103
        self.user.userplan_set.all.return_value = []
        config = mock_pipeline_config("wca-onprem", model_id=None)
        self.config = config

    def test_get_api_key(self):
        self.config.username = "username"
        self.config.api_key = "12345"
        model_client = WCAOnPremCompletionsPipeline(self.config)
        api_key = model_client.get_api_key(Mock())
        self.assertEqual(api_key, "12345")

    def test_get_api_key_without_setting(self):
        self.config.username = "username"
        self.config.api_key = None
        with self.assertRaises(WcaKeyNotFound):
            WCAOnPremCompletionsPipeline(self.config)

    def test_get_model_id(self):
        self.config.username = "username"
        self.config.api_key = "12345"
        self.config.model_id = "model-name"
        model_client = WCAOnPremCompletionsPipeline(self.config)
        model_id = model_client.get_model_id(self.user)
        self.assertEqual(model_id, "model-name")

    def test_get_model_id_with_override(self):
        self.config.username = "username"
        self.config.api_key = "12345"
        self.config.model_id = "model-name"
        model_client = WCAOnPremCompletionsPipeline(self.config)
        model_id = model_client.get_model_id(self.user, "override-model-name")
        self.assertEqual(model_id, "override-model-name")

    def test_get_model_id_without_setting(self):
        self.config.username = "username"
        self.config.api_key = "12345"
        self.config.model_id = None
        model_client = WCAOnPremCompletionsPipeline(self.config)
        with self.assertRaises(WcaModelIdNotFound):
            model_client.get_model_id(self.user)


class TestWCAOnPremCodegen(WisdomServiceLogAwareTestCase):
    prompt = "- name: install ffmpeg on Red Hat Enterprise Linux"
    suggestion_id = "suggestion_id"
    user_uuid = str(uuid.uuid4())
    token = base64.b64encode(bytes("username:12345", "ascii")).decode("ascii")
    codegen_data = {
        "model_id": "model-name",
        "prompt": f"{prompt}\n",
    }
    request_headers = {
        "Authorization": f"ZenApiKey {token}",
        WCA_REQUEST_ID_HEADER: suggestion_id,
        WCA_REQUEST_USER_UUID_HEADER: user_uuid,
    }
    model_input = {
        "instances": [
            {
                "context": "",
                "prompt": prompt,
            }
        ]
    }

    def setUp(self):
        super().setUp()
        config = mock_pipeline_config(
            "wca-onprem",
            api_key="12345",
            model_id="model-name",
            retry_count=1,
            username="username",
            timeout=None,
            verify_ssl=True,
        )
        self.config = config
        self.model_client = WCAOnPremCompletionsPipeline(self.config)
        self.model_client.session.post = Mock(return_value=MockResponse(json={}, status_code=200))

    def test_headers(self):
        mock_request = Mock()
        mock_request.user = Mock()
        mock_request.user.uuid = self.user_uuid

        self.model_client.invoke(
            CompletionsParameters.init(
                request=mock_request, model_input=self.model_input, suggestion_id=self.suggestion_id
            ),
        )
        self.model_client.session.post.assert_called_once_with(
            "http://localhost/v1/wca/codegen/ansible",
            headers=self.request_headers,
            json=self.codegen_data,
            timeout=None,
        )

    def test_disabled_model_server_ssl(self):
        mock_request = Mock()
        mock_request.user = Mock()
        mock_request.user.uuid = self.user_uuid
        self.config.verify_ssl = False
        self.model_client.invoke(
            CompletionsParameters.init(
                request=mock_request, model_input=self.model_input, suggestion_id=self.suggestion_id
            ),
        )
        self.model_client.session.post.assert_called_once_with(
            "http://localhost/v1/wca/codegen/ansible",
            headers=self.request_headers,
            json=self.codegen_data,
            timeout=None,
        )


def mock_anonymize(x):
    if isinstance(x, str):
        return f"anonymized_{x}"
    elif isinstance(x, dict):
        return {k: mock_anonymize(v) for k, v in x.items()}
    elif isinstance(x, list):
        return [mock_anonymize(item) for item in x]
    return x


class TestWCAAnonymization(WisdomServiceAPITestCaseBaseOIDC, WisdomServiceLogAwareTestCase):
    def setUp(self):
        super().setUp()
        self.config = mock_pipeline_config("wca")

        self.mock_request = Mock()
        self.mock_request.user = self.user

        # Mock anonymizer for testing
        self.anonymizer_patcher = patch(
            "ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_base.anonymizer"
        )
        self.mock_anonymizer = self.anonymizer_patcher.start()
        self.mock_anonymizer.anonymize_struct = mock_anonymize

    def tearDown(self):
        self.anonymizer_patcher.stop()
        super().tearDown()

    def test_should_anonymize_no_organization(self):
        """Test that anonymization is enabled by default if user has no organization"""
        self.model_client = WCASaaSPlaybookGenerationPipeline(self.config)
        self.mock_request.user.organization = None
        self.assertTrue(self.model_client.should_anonymize(self.mock_request))

    def test_should_anonymize_with_organization_enabled(self):
        """Test that anonymization follows organization setting when enabled"""
        self.model_client = WCASaaSPlaybookGenerationPipeline(self.config)
        self.mock_request.user.organization.enable_anonymization = True
        self.assertTrue(self.model_client.should_anonymize(self.mock_request))

    def test_should_anonymize_with_organization_disabled(self):
        """Test that anonymization follows organization setting when disabled"""
        self.model_client = WCASaaSPlaybookGenerationPipeline(self.config)
        self.mock_request.user.organization.enable_anonymization = False
        self.assertFalse(self.model_client.should_anonymize(self.mock_request))

    def test_should_anonymize_global_override(self):
        """Test that global setting overrides organization settings"""
        # Test with no organization
        self.model_client = WCASaaSPlaybookGenerationPipeline(self.config)
        self.mock_request.user.organization = None
        self.config.enable_anonymization = False
        self.assertFalse(self.model_client.should_anonymize(self.mock_request))

    def test_playbook_generation_no_anonymization(self):
        """Test that playbook generation doesn't anonymize when disabled"""
        self.model_client = WCASaaSPlaybookGenerationPipeline(self.config)
        self.user.organization.enable_anonymization = False
        self.model_client.get_token = Mock(return_value={"access_token": "test-token"})
        self.model_client.session.post = Mock(
            return_value=MockResponse(
                json={"playbook": "test", "outline": "", "warnings": []}, status_code=200
            )
        )

        test_text = "Install nginx on RHEL"
        test_prompt = "Custom prompt"
        self.model_client.invoke(
            PlaybookGenerationParameters.init(
                request=self.mock_request, text=test_text, custom_prompt=test_prompt
            )
        )

        # Verify the data sent to the API wasn't anonymized
        call_args = self.model_client.session.post.call_args
        self.assertEqual(call_args[1]["json"]["text"], test_text)
        self.assertEqual(call_args[1]["json"]["custom_prompt"], test_prompt + "\n")

    def test_role_generation_no_anonymization(self):
        """Test that role generation doesn't anonymize when disabled"""
        self.model_client = WCASaaSRoleGenerationPipeline(self.config)
        self.user.organization.enable_anonymization = False
        self.model_client.get_token = Mock(return_value={"access_token": "test-token"})
        self.model_client.session.post = Mock(
            return_value=MockResponse(
                json={"name": "test", "files": [], "outline": "", "warnings": []}, status_code=200
            )
        )

        test_text = "Create a role to install nginx"
        test_name = "nginx_installer"
        self.model_client.invoke(
            RoleGenerationParameters.init(request=self.mock_request, text=test_text, name=test_name)
        )

        # Verify the data sent to the API wasn't anonymized
        call_args = self.model_client.session.post.call_args
        self.assertEqual(call_args[1]["json"]["text"], test_text)
        self.assertEqual(call_args[1]["json"]["name"], test_name)

    def test_playbook_explanation_no_anonymization(self):
        """Test that playbook explanation doesn't anonymize when disabled"""
        self.model_client = WCASaaSPlaybookExplanationPipeline(self.config)
        self.user.organization.enable_anonymization = False
        self.model_client.get_token = Mock(return_value={"access_token": "test-token"})
        self.model_client.session.post = Mock(
            return_value=MockResponse(json={"explanation": "test explanation"}, status_code=200)
        )

        test_content = "- name: Install nginx\n  apt: name=nginx state=present"
        test_prompt = "Explain this playbook"
        self.model_client.invoke(
            PlaybookExplanationParameters.init(
                request=self.mock_request, content=test_content, custom_prompt=test_prompt
            )
        )

        # Verify the data sent to the API wasn't anonymized
        call_args = self.model_client.session.post.call_args
        self.assertEqual(call_args[1]["json"]["playbook"], test_content)
        self.assertEqual(call_args[1]["json"]["custom_prompt"], test_prompt + "\n")

    def test_role_explanation_no_anonymization(self):
        """Test that role explanation doesn't anonymize when disabled"""
        self.model_client = WCASaaSRoleExplanationPipeline(self.config)
        self.user.organization.enable_anonymization = False
        self.model_client.get_token = Mock(return_value={"access_token": "test-token"})
        self.model_client.session.post = Mock(
            return_value=MockResponse(json={"explanation": "test explanation"}, status_code=200)
        )

        test_files = [
            {
                "name": "tasks/main.yml",
                "content": "- name: Install nginx\n  apt: name=nginx state=present",
            }
        ]
        test_role_name = "nginx_installer"
        self.model_client.invoke(
            RoleExplanationParameters.init(
                request=self.mock_request, files=test_files, role_name=test_role_name
            )
        )

        # Verify the data sent to the API wasn't anonymized
        call_args = self.model_client.session.post.call_args
        self.assertEqual(call_args[1]["json"]["files"], test_files)
        self.assertEqual(call_args[1]["json"]["role_name"], test_role_name)

    def test_playbook_generation_with_anonymization(self):
        """Test that playbook generation anonymizes when enabled"""
        self.model_client = WCASaaSPlaybookGenerationPipeline(self.config)
        self.mock_request.user.organization.enable_anonymization = True
        self.model_client.get_token = Mock(return_value={"access_token": "test-token"})
        self.model_client.session.post = Mock(
            return_value=MockResponse(
                json={"playbook": "test", "outline": "", "warnings": []}, status_code=200
            )
        )

        test_text = "Install nginx on RHEL"
        test_prompt = "Custom prompt"
        self.model_client.invoke(
            PlaybookGenerationParameters.init(
                request=self.mock_request, text=test_text, custom_prompt=test_prompt
            )
        )

        # Verify the data sent to the API was anonymized
        call_args = self.model_client.session.post.call_args
        self.assertEqual(call_args[1]["json"]["text"], "anonymized_Install nginx on RHEL")
        self.assertEqual(call_args[1]["json"]["custom_prompt"], "anonymized_Custom prompt\n")

    def test_role_generation_with_anonymization(self):
        """Test that role generation anonymizes when enabled"""
        self.model_client = WCASaaSRoleGenerationPipeline(self.config)
        self.mock_request.user.organization.enable_anonymization = True
        self.model_client.get_token = Mock(return_value={"access_token": "test-token"})
        self.model_client.session.post = Mock(
            return_value=MockResponse(
                json={"name": "test", "files": [], "outline": "", "warnings": []}, status_code=200
            )
        )

        test_text = "Create a role to install nginx"
        test_name = "nginx_installer"
        self.model_client.invoke(
            RoleGenerationParameters.init(request=self.mock_request, text=test_text, name=test_name)
        )

        # Verify the data sent to the API was anonymized
        call_args = self.model_client.session.post.call_args
        self.assertEqual(call_args[1]["json"]["text"], "anonymized_Create a role to install nginx")
        self.assertEqual(call_args[1]["json"]["name"], "anonymized_nginx_installer")

    def test_playbook_explanation_with_anonymization(self):
        """Test that playbook explanation anonymizes when enabled"""
        self.model_client = WCASaaSPlaybookExplanationPipeline(self.config)
        self.mock_request.user.organization.enable_anonymization = True
        self.model_client.get_token = Mock(return_value={"access_token": "test-token"})
        self.model_client.session.post = Mock(
            return_value=MockResponse(json={"explanation": "test explanation"}, status_code=200)
        )

        test_content = "- name: Install nginx\n  apt: name=nginx state=present"
        test_prompt = "Explain this playbook"
        self.model_client.invoke(
            PlaybookExplanationParameters.init(
                request=self.mock_request, content=test_content, custom_prompt=test_prompt
            )
        )

        # Verify the data sent to the API was anonymized
        call_args = self.model_client.session.post.call_args
        self.assertEqual(
            call_args[1]["json"]["playbook"],
            "anonymized_- name: Install nginx\n  apt: name=nginx state=present",
        )
        self.assertEqual(
            call_args[1]["json"]["custom_prompt"], "anonymized_Explain this playbook\n"
        )

    def test_role_explanation_with_anonymization(self):
        """Test that role explanation anonymizes when enabled"""
        self.model_client = WCASaaSRoleExplanationPipeline(self.config)
        self.mock_request.user.organization.enable_anonymization = True
        self.model_client.get_token = Mock(return_value={"access_token": "test-token"})
        self.model_client.session.post = Mock(
            return_value=MockResponse(json={"explanation": "test explanation"}, status_code=200)
        )

        test_files = [
            {
                "name": "tasks/main.yml",
                "content": "- name: Install nginx\n  apt: name=nginx state=present",
            }
        ]
        test_role_name = "nginx_installer"
        self.model_client.invoke(
            RoleExplanationParameters.init(
                request=self.mock_request, files=test_files, role_name=test_role_name
            )
        )

        # Verify the data sent to the API was anonymized
        call_args = self.model_client.session.post.call_args
        self.assertEqual(
            call_args[1]["json"]["files"][0]["content"],
            "anonymized_- name: Install nginx\n  apt: name=nginx state=present",
        )
        self.assertEqual(call_args[1]["json"]["role_name"], "anonymized_nginx_installer")


class TestWCAOnPremCodematch(WisdomServiceLogAwareTestCase):
    def test_headers(self):
        suggestions = [
            "- name: install ffmpeg on Red Hat Enterprise Linux\n  "
            "ansible.builtin.package:\n    name:\n      - ffmpeg\n    state: present\n",
            "- name: This is another test",
        ]
        model_input = {"suggestions": suggestions}
        data = {
            "model_id": "model-name",
            "input": suggestions,
        }
        token = base64.b64encode(bytes("username:12345", "ascii")).decode("ascii")

        request_headers = {
            "Authorization": f"ZenApiKey {token}",
        }

        model_client = WCAOnPremContentMatchPipeline(
            mock_pipeline_config(
                "wca-onprem",
                api_key="12345",
                model_id="model_name",
                retry_count=1,
                username="username",
                timeout=None,
                verify_ssl=True,
            )
        )
        model_client.session.post = Mock(return_value=MockResponse(json={}, status_code=200))

        model_client.invoke(
            ContentMatchParameters.init(
                request=Mock(), model_input=model_input, model_id="model-name"
            )
        )

        model_client.session.post.assert_called_once_with(
            "http://localhost/v1/wca/codematch/ansible",
            headers=request_headers,
            json=data,
            timeout=None,
        )
