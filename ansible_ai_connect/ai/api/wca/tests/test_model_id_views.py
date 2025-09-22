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

from http import HTTPStatus
from unittest.mock import Mock, patch

from django.apps import apps
from django.test import override_settings
from django.urls import resolve
from django.utils import timezone
from oauth2_provider.contrib.rest_framework import IsAuthenticatedOrTokenHasScope
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated

import ansible_ai_connect.ai.api.aws.wca_secret_manager
import ansible_ai_connect.ai.apps
from ansible_ai_connect.ai.api.aws.exceptions import WcaSecretManagerError
from ansible_ai_connect.ai.api.aws.wca_secret_manager import AWSSecretManager, Suffixes
from ansible_ai_connect.ai.api.model_pipelines.exceptions import (
    WcaEmptyResponse,
    WcaInvalidModelId,
    WcaKeyNotFound,
    WcaUserTrialExpired,
)
from ansible_ai_connect.ai.api.model_pipelines.pipelines import ModelPipelineCompletions
from ansible_ai_connect.ai.api.permissions import (
    IsOrganisationAdministrator,
    IsOrganisationLightspeedSubscriber,
    IsWCASaaSModelPipeline,
)
from ansible_ai_connect.ai.api.tests.test_views import WisdomServiceAPITestCaseBase
from ansible_ai_connect.organizations.models import ExternalOrganization
from ansible_ai_connect.test_utils import (
    APIVersionTestCaseBase,
    WisdomAppsBackendMocking,
    WisdomLogAwareMixin,
    WisdomServiceAPITestCaseBaseOIDC,
)

VALIDATE_PROMPT = "---\n- hosts: all\n  tasks:\n  - name: install ssh\n"


@override_settings(DEPLOYMENT_MODE="saas")
@override_settings(WCA_SECRET_BACKEND_TYPE="aws_sm")
@patch.object(IsOrganisationAdministrator, "has_permission", return_value=True)
@patch.object(IsOrganisationLightspeedSubscriber, "has_permission", return_value=True)
class TestWCAModelIdView(
    APIVersionTestCaseBase,
    WisdomAppsBackendMocking,
    WisdomServiceAPITestCaseBaseOIDC,
    WisdomLogAwareMixin,
):
    def setUp(self):
        super().setUp()
        self.secret_manager_patcher = patch.object(
            ansible_ai_connect.ai.apps, "AWSSecretManager", spec=AWSSecretManager
        )
        self.secret_manager_patcher.start()

        self.wca_client_patcher = patch.object(
            apps.get_app_config("ai")._pipeline_factory, "get_pipeline", return_value=Mock()
        )
        self.wca_client_patcher.start()

    def tearDown(self):
        self.secret_manager_patcher.stop()
        self.wca_client_patcher.stop()
        super().tearDown()

    def test_get_model_id_authentication_error(self, *args):
        # self.client.force_authenticate(user=self.user)
        r = self.client.get(self.api_version_reverse("wca_model_id"))
        self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_get_key_without_org_id(self, *args):
        self.user.organization = None
        self.client.force_authenticate(user=self.user)

        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.get(self.api_version_reverse("wca_model_id"))
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            self.assert_segment_log(log, "modelIdGet", None)

    def test_permission_classes(self, *args):
        url = self.api_version_reverse("wca_model_id")
        view = resolve(url).func.view_class

        required_permissions = [
            IsAuthenticated,
            IsAuthenticatedOrTokenHasScope,
            IsOrganisationAdministrator,
            IsOrganisationLightspeedSubscriber,
            IsWCASaaSModelPipeline,
        ]
        self.assertEqual(len(view.permission_classes), len(required_permissions))
        for permission in required_permissions:
            self.assertTrue(permission in view.permission_classes)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_get_model_id_when_undefined(self, *args):
        self.user.organization = ExternalOrganization.objects.get_or_create(id=123)[0]
        mock_secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        self.client.force_authenticate(user=self.user)
        mock_secret_manager.get_secret.return_value = None

        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.get(self.api_version_reverse("wca_model_id"))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            mock_secret_manager.get_secret.assert_called_with(123, Suffixes.MODEL_ID)
            self.assert_segment_log(log, "modelIdGet", None)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_get_model_id_when_defined(self, *args):
        self._test_get_model_id_when_defined(False)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_get_model_id_when_defined_seated_user(self, *args):
        self._test_get_model_id_when_defined(True)

    def _test_get_model_id_when_defined(self, has_seat):
        self.user.organization = ExternalOrganization.objects.get_or_create(id=123)[0]
        self.user.rh_user_has_seat = has_seat
        mock_secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        self.client.force_authenticate(user=self.user)
        date_time = timezone.now().isoformat()
        mock_secret_manager.get_secret.return_value = {
            "SecretString": "secret_model_id",
            "CreatedDate": date_time,
        }

        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.get(self.api_version_reverse("wca_model_id"))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            self.assertEqual(r.data["model_id"], "secret_model_id")
            self.assertEqual(r.data["last_update"], date_time)
            mock_secret_manager.get_secret.assert_called_with(123, Suffixes.MODEL_ID)
            self.assert_segment_log(log, "modelIdGet", None)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_get_model_id_when_defined_throws_exception(self, *args):
        self.user.organization = ExternalOrganization.objects.get_or_create(id=123)[0]
        mock_secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        self.client.force_authenticate(user=self.user)
        mock_secret_manager.get_secret.side_effect = WcaSecretManagerError("Test")

        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.get(self.api_version_reverse("wca_model_id"))
            self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
            self.assertInLog("ansible_ai_connect.ai.api.aws.exceptions.WcaSecretManagerError", log)
            self.assert_segment_log(log, "modelIdGet", "WcaSecretManagerError")

    def test_set_model_id_authentication_error(self, *args):
        # self.client.force_authenticate(user=self.user)
        r = self.client.post(self.api_version_reverse("wca_model_id"))
        self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_set_key_without_org_id(self, *args):
        self.client.force_authenticate(user=self.user)

        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(self.api_version_reverse("wca_model_id"))
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            self.assert_segment_log(log, "modelIdSet", None)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_set_model_id(self, *args):
        self._test_set_model_id(False)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_set_model_id_seated_user(self, *args):
        self._test_set_model_id(True)

    def _test_set_model_id(self, has_seat):
        self.user.organization = ExternalOrganization.objects.get_or_create(id=123)[0]
        self.user.rh_user_has_seat = has_seat
        mock_secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        mock_wca_client: ModelPipelineCompletions = apps.get_app_config("ai").get_model_pipeline(
            ModelPipelineCompletions
        )
        self.client.force_authenticate(user=self.user)

        # ModelId should initially not exist
        mock_secret_manager.get_secret.return_value = None
        r = self.client.get(self.api_version_reverse("wca_model_id"))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        mock_secret_manager.get_secret.assert_called_with(123, Suffixes.MODEL_ID)

        # Set ModelId
        api_key_value = "someAPIKey"
        model_id_value = "secret_model_id"
        mock_secret_manager.get_secret.return_value = {"SecretString": api_key_value}

        expected_headers = {"Authorization": f"Bearer {api_key_value}", "X-Test-Header-Set": "true"}
        mock_wca_client.get_request_headers.return_value = expected_headers
        mock_wca_client.infer_from_parameters.reset_mock(side_effect=True)
        mock_wca_client.infer_from_parameters.side_effect = None

        with self.assertLogs(logger="ansible_ai_connect.users.signals", level="DEBUG") as signals:
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(
                    self.api_version_reverse("wca_model_id"),
                    data='{ "model_id": "secret_model_id" }',
                    content_type="application/json",
                )

                self.assertEqual(r.status_code, HTTPStatus.NO_CONTENT)

                mock_wca_client.get_request_headers.assert_called_once_with(
                    api_key=api_key_value, identifier=None, lightspeed_user_uuid=None
                )
                mock_wca_client.infer_from_parameters.assert_called_once_with(
                    model_id_value,
                    "",
                    VALIDATE_PROMPT,
                    headers=expected_headers,
                )
                mock_secret_manager.save_secret.assert_called_with(
                    123, Suffixes.MODEL_ID, model_id_value
                )
                self.assert_segment_log(log, "modelIdSet", None)

            # Check audit entry
            self.assertInLog(
                f"User: '{self.user}' set WCA Model Id for "
                f"Organisation '{self.user.organization.id}'",
                signals,
            )

        # Check ModelId was stored
        mock_secret_manager.get_secret.return_value = {
            "SecretString": "secret_model_id",
            "CreatedDate": timezone.now().isoformat(),
        }
        r = self.client.get(self.api_version_reverse("wca_model_id"))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertEqual(r.data["model_id"], "secret_model_id")
        mock_secret_manager.get_secret.assert_called_with(123, Suffixes.MODEL_ID)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_set_model_id_not_valid(self, *args):
        self.user.organization = ExternalOrganization.objects.get_or_create(id=123)[0]
        mock_secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        mock_wca_client: ModelPipelineCompletions = apps.get_app_config("ai").get_model_pipeline(
            ModelPipelineCompletions
        )
        self.client.force_authenticate(user=self.user)

        # ModelId should initially not exist
        mock_secret_manager.get_secret.return_value = None

        r = self.client.get(self.api_version_reverse("wca_model_id"))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        mock_secret_manager.get_secret.assert_called_with(123, Suffixes.MODEL_ID)

        # Set ModelId
        mock_secret_manager.get_secret.return_value = {"SecretString": "someAPIKey"}

        with self.assertLogs(logger="root", level="DEBUG") as log:
            mock_wca_client.infer_from_parameters.side_effect = ValidationError
            r = self.client.post(
                self.api_version_reverse("wca_model_id"),
                data='{ "model_id": "secret_model_id" }',
                content_type="application/json",
            )
            mock_wca_client.infer_from_parameters.assert_called()
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            self.assertInLog("ValidationError", log)
            self.assert_segment_log(log, "modelIdSet", "ValidationError")

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_set_model_id_throws_secret_manager_exception(self, *args):
        self.user.organization = ExternalOrganization.objects.get_or_create(id=123)[0]
        self.client.force_authenticate(user=self.user)
        mock_secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        mock_secret_manager.save_secret.side_effect = WcaSecretManagerError("Test")

        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(
                self.api_version_reverse("wca_model_id"),
                data='{ "model_id": "secret_model_id" }',
                content_type="application/json",
            )
            self.assertEqual(r.status_code, HTTPStatus.SERVICE_UNAVAILABLE)
            self.assertInLog("ansible_ai_connect.ai.api.aws.exceptions.WcaSecretManagerError", log)
            self.assert_segment_log(log, "modelIdSet", "WcaSecretManagerError")

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_set_model_id_throws_validation_exception(self, *args):
        self.user.organization = ExternalOrganization.objects.get_or_create(id=123)[0]
        self.client.force_authenticate(user=self.user)
        mock_secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        mock_secret_manager.save_secret.side_effect = WcaSecretManagerError("Test")

        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(
                self.api_version_reverse("wca_model_id"),
                data='{ "unknown_json_field": "secret_model_id" }',
                content_type="application/json",
            )
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            self.assert_segment_log(log, "modelIdSet", "ValidationError")

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_set_model_id_empty_response(self, *args):
        self.user.organization = ExternalOrganization.objects.get_or_create(id=123)[0]
        mock_secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        mock_wca_client: ModelPipelineCompletions = apps.get_app_config("ai").get_model_pipeline(
            ModelPipelineCompletions
        )
        self.client.force_authenticate(user=self.user)

        # Set ModelId
        mock_secret_manager.get_secret.return_value = {"SecretString": "someAPIKey"}
        mock_wca_client.infer_from_parameters = Mock(side_effect=WcaEmptyResponse)
        with self.assertLogs(logger="root", level="INFO") as log:
            r = self.client.post(
                self.api_version_reverse("wca_model_id"),
                data='{ "model_id": "secret_model_id" }',
                content_type="application/json",
            )

            self.assertEqual(r.status_code, HTTPStatus.NO_CONTENT)
            self.assertInLog(
                "WCA returned an empty response validating model_id 'secret_model_id'", log
            )
            mock_secret_manager.save_secret.assert_called_with(
                123, Suffixes.MODEL_ID, "secret_model_id"
            )


@patch.object(IsOrganisationAdministrator, "has_permission", return_value=True)
@patch.object(IsOrganisationLightspeedSubscriber, "has_permission", return_value=False)
class TestWCAModelIdViewAsNonSubscriber(
    APIVersionTestCaseBase, WisdomAppsBackendMocking, WisdomServiceAPITestCaseBase
):
    def test_get_model_id_as_non_subscriber(self, *args):
        self.user.organization = ExternalOrganization.objects.get_or_create(id=123)[0]
        self.client.force_authenticate(user=self.user)
        r = self.client.get(self.api_version_reverse("wca_model_id"))
        self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)


@override_settings(DEPLOYMENT_MODE="saas")
@override_settings(WCA_SECRET_BACKEND_TYPE="aws_sm")
@patch.object(IsOrganisationAdministrator, "has_permission", return_value=True)
@patch.object(IsOrganisationLightspeedSubscriber, "has_permission", return_value=True)
class TestWCAModelIdValidatorView(
    APIVersionTestCaseBase,
    WisdomAppsBackendMocking,
    WisdomServiceAPITestCaseBase,
    WisdomLogAwareMixin,
):
    def setUp(self):
        super().setUp()
        self.secret_manager_patcher = patch.object(
            ansible_ai_connect.ai.apps, "AWSSecretManager", spec=AWSSecretManager
        )
        self.secret_manager_patcher.start()

        self.wca_client_patcher = patch.object(
            apps.get_app_config("ai")._pipeline_factory, "get_pipeline", return_value=Mock()
        )
        self.wca_client_patcher.start()

    def tearDown(self):
        self.secret_manager_patcher.stop()
        self.wca_client_patcher.stop()
        super().tearDown()

    def test_validate(self, *args):
        self.user.organization = ExternalOrganization.objects.get_or_create(id=123)[0]
        self.client.force_authenticate(user=self.user)
        mock_wca_client: ModelPipelineCompletions = apps.get_app_config("ai").get_model_pipeline(
            ModelPipelineCompletions
        )
        mock_wca_client.infer = Mock(return_value={})

        r = self.client.get(self.api_version_reverse("wca_model_id_validator"))
        self.assertEqual(r.status_code, HTTPStatus.OK)

    def test_validate_error_authentication(self, *args):
        # self.client.force_authenticate(user=self.user)
        r = self.client.get(self.api_version_reverse("wca_model_id_validator"))
        self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_validate_error_no_org_id(self, *args):
        self.user.organization = None
        self.client.force_authenticate(user=self.user)

        r = self.client.get(self.api_version_reverse("wca_model_id_validator"))
        self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_validate_error_no_api_key(self, *args):
        self.user.organization = ExternalOrganization.objects.get_or_create(id=123)[0]
        mock_secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        self.client.force_authenticate(user=self.user)

        def mock_get_secret_no_api_key(*args, **kwargs):
            if args[1] == Suffixes.MODEL_ID:
                return {"SecretString": "some_model_id"}
            return {"SecretString": None}

        mock_secret_manager.get_secret.side_effect = mock_get_secret_no_api_key
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.get(self.api_version_reverse("wca_model_id_validator"))
            self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
            self.assertInLog(
                "ansible_ai_connect.ai.api.model_pipelines.exceptions.WcaKeyNotFound", log
            )
            self.assert_segment_log(log, "modelIdValidate", "WcaKeyNotFound")

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_validate_error_no_model_id(self, *args):
        self.user.organization = ExternalOrganization.objects.get_or_create(id=123)[0]
        mock_secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        self.client.force_authenticate(user=self.user)

        def mock_get_secret_no_model_id(*args, **kwargs):
            if args[1] == Suffixes.API_KEY:
                return {"SecretString": "some_api_key"}
            return {"SecretString": None}

        mock_secret_manager.get_secret.side_effect = mock_get_secret_no_model_id
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.get(self.api_version_reverse("wca_model_id_validator"))
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            self.assertInLog(
                "ansible_ai_connect.ai.api.model_pipelines.exceptions.WcaModelIdNotFound", log
            )
            self.assert_segment_log(log, "modelIdValidate", "WcaModelIdNotFound")

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_validate_ok(self, *args):
        self._test_validate_ok(False)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_validate_ok_seated_user(self, *args):
        self._test_validate_ok(True)

    def _test_validate_ok(self, has_seat):
        self.user.organization = ExternalOrganization.objects.get_or_create(id=123)[0]
        self.user.rh_user_has_seat = has_seat
        mock_secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        mock_wca_client: ModelPipelineCompletions = apps.get_app_config("ai").get_model_pipeline(
            ModelPipelineCompletions
        )
        self.client.force_authenticate(user=self.user)

        api_key_value = "some_api_key_for_validate"
        model_id_value = "model_id_for_validate"

        def mock_get_secret_side_effect(*args, **kwargs):
            if args[1] == Suffixes.API_KEY:
                return {"SecretString": api_key_value}
            if args[1] == Suffixes.MODEL_ID:
                return {"SecretString": model_id_value}
            return None

        mock_secret_manager.get_secret.side_effect = mock_get_secret_side_effect

        expected_headers = {
            "Authorization": f"Bearer {api_key_value}",
            "X-Test-Header-Validate": "true",
        }
        mock_wca_client.get_request_headers.return_value = expected_headers
        mock_wca_client.infer_from_parameters.reset_mock(side_effect=True)
        mock_wca_client.infer_from_parameters.side_effect = None

        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.get(self.api_version_reverse("wca_model_id_validator"))
            self.assertEqual(r.status_code, HTTPStatus.OK)

            mock_wca_client.get_request_headers.assert_called_once_with(
                api_key=api_key_value, identifier=None, lightspeed_user_uuid=None
            )
            mock_wca_client.infer_from_parameters.assert_called_once_with(
                model_id_value,
                "",
                VALIDATE_PROMPT,
                headers=expected_headers,
            )
            self.assert_segment_log(log, "modelIdValidate", None)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_validate_error_wrong_model_id(self, *args):
        self.user.organization = ExternalOrganization.objects.get_or_create(id=123)[0]
        mock_wca_client: ModelPipelineCompletions = apps.get_app_config("ai").get_model_pipeline(
            ModelPipelineCompletions
        )
        self.client.force_authenticate(user=self.user)
        mock_wca_client.infer_from_parameters = Mock(side_effect=ValidationError)

        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.get(self.api_version_reverse("wca_model_id_validator"))
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            self.assertInLog("ValidationError", log)
            self.assert_segment_log(log, "modelIdValidate", "ValidationError")

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_validate_error_api_key_not_found(self, *args):
        self.user.organization = ExternalOrganization.objects.get_or_create(id=123)[0]
        mock_wca_client: ModelPipelineCompletions = apps.get_app_config("ai").get_model_pipeline(
            ModelPipelineCompletions
        )
        self.client.force_authenticate(user=self.user)
        mock_wca_client.infer_from_parameters = Mock(side_effect=WcaKeyNotFound)

        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.get(self.api_version_reverse("wca_model_id_validator"))
            self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
            self.assertInLog(
                "ansible_ai_connect.ai.api.model_pipelines.exceptions.WcaKeyNotFound", log
            )
            self.assert_segment_log(log, "modelIdValidate", "WcaKeyNotFound")

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_validate_error_user_trial_expired(self, *args):
        self.user.organization = ExternalOrganization.objects.get_or_create(id=123)[0]
        mock_wca_client: ModelPipelineCompletions = apps.get_app_config("ai").get_model_pipeline(
            ModelPipelineCompletions
        )
        self.client.force_authenticate(user=self.user)
        mock_wca_client.infer_from_parameters = Mock(side_effect=WcaUserTrialExpired)

        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.get(self.api_version_reverse("wca_model_id_validator"))
            self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
            self.assertEqual(r.data["code"], "permission_denied__user_trial_expired")
            self.assertEqual(
                r.data["message"], "User trial expired. Please contact your administrator."
            )
            self.assertInLog(
                "ansible_ai_connect.ai.api.model_pipelines.exceptions.WcaUserTrialExpired", log
            )
            self.assert_segment_log(log, "trialExpired", None, type="modelIdValidate")

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_validate_error_model_id_bad_request(self, *args):
        self.user.organization = ExternalOrganization.objects.get_or_create(id=123)[0]
        mock_wca_client: ModelPipelineCompletions = apps.get_app_config("ai").get_model_pipeline(
            ModelPipelineCompletions
        )
        self.client.force_authenticate(user=self.user)
        mock_wca_client.infer_from_parameters = Mock(side_effect=WcaInvalidModelId)

        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.get(self.api_version_reverse("wca_model_id_validator"))
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            self.assertInLog(
                "ansible_ai_connect.ai.api.model_pipelines.exceptions.WcaInvalidModelId", log
            )
            self.assert_segment_log(log, "modelIdValidate", "WcaInvalidModelId")

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_validate_error_model_id_exception(self, *args):
        self.user.organization = ExternalOrganization.objects.get_or_create(id=123)[0]
        mock_wca_client: ModelPipelineCompletions = apps.get_app_config("ai").get_model_pipeline(
            ModelPipelineCompletions
        )
        self.client.force_authenticate(user=self.user)
        mock_wca_client.infer_from_parameters = Mock(side_effect=Exception)

        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.get(self.api_version_reverse("wca_model_id_validator"))
            self.assertEqual(r.status_code, HTTPStatus.SERVICE_UNAVAILABLE)
            self.assertInLog("Exception", log)
            self.assert_segment_log(log, "modelIdValidate", "Exception")

    @override_settings(WCA_SECRET_BACKEND_TYPE="dummy")
    @override_settings(WCA_SECRET_DUMMY_SECRETS="123:my-model-id")
    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_validate_error_model_id_empty_response(self, *args):
        self.user.organization = ExternalOrganization.objects.get_or_create(id=123)[0]
        mock_wca_client: ModelPipelineCompletions = apps.get_app_config("ai").get_model_pipeline(
            ModelPipelineCompletions
        )
        self.client.force_authenticate(user=self.user)
        mock_wca_client.infer_from_parameters = Mock(side_effect=WcaEmptyResponse)

        with self.assertLogs(logger="root", level="INFO") as log:
            r = self.client.get(self.api_version_reverse("wca_model_id_validator"))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            self.assertInLog(
                "WCA returned an empty response validating model_id 'my-model-id'", log
            )
