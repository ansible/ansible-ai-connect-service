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
from django.urls import resolve, reverse
from django.utils import timezone
from oauth2_provider.contrib.rest_framework import IsAuthenticatedOrTokenHasScope
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated

import ansible_ai_connect.ai.api.aws.wca_secret_manager
import ansible_ai_connect.ai.apps
from ansible_ai_connect.ai.api.aws.exceptions import WcaSecretManagerError
from ansible_ai_connect.ai.api.aws.wca_secret_manager import AWSSecretManager, Suffixes
from ansible_ai_connect.ai.api.model_client.exceptions import (
    WcaInvalidModelId,
    WcaUserTrialExpired,
)
from ansible_ai_connect.ai.api.model_client.wca_client import WCAClient, WcaKeyNotFound
from ansible_ai_connect.ai.api.permissions import (
    AcceptedTermsPermission,
    IsOrganisationAdministrator,
    IsOrganisationLightspeedSubscriber,
)
from ansible_ai_connect.ai.api.tests.test_views import WisdomServiceAPITestCaseBase
from ansible_ai_connect.organizations.models import Organization
from ansible_ai_connect.test_utils import WisdomAppsBackendMocking, WisdomLogAwareMixin


@override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="wca")
@override_settings(WCA_SECRET_BACKEND_TYPE="aws_sm")
@patch.object(IsOrganisationAdministrator, "has_permission", return_value=True)
@patch.object(IsOrganisationLightspeedSubscriber, "has_permission", return_value=True)
class TestWCAModelIdView(
    WisdomAppsBackendMocking, WisdomServiceAPITestCaseBase, WisdomLogAwareMixin
):
    def setUp(self):
        super().setUp()
        self.secret_manager_patcher = patch.object(
            ansible_ai_connect.ai.apps, "AWSSecretManager", spec=AWSSecretManager
        )
        self.secret_manager_patcher.start()

        self.wca_client_patcher = patch.object(
            ansible_ai_connect.ai.apps, "WCAClient", spec=WCAClient
        )
        self.wca_client_patcher.start()
        apps.get_app_config("ai").ready()

    def tearDown(self):
        self.secret_manager_patcher.stop()
        self.wca_client_patcher.stop()
        super().tearDown()

    def test_get_model_id_authentication_error(self, *args):
        # self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse("wca_model_id"))
        self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_get_key_without_org_id(self, *args):
        self.client.force_authenticate(user=self.user)

        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.get(reverse("wca_model_id"))
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            self.assert_segment_log(log, "modelIdGet", None)

    def test_permission_classes(self, *args):
        url = reverse("wca_model_id")
        view = resolve(url).func.view_class

        required_permissions = [
            IsAuthenticated,
            IsAuthenticatedOrTokenHasScope,
            IsOrganisationAdministrator,
            IsOrganisationLightspeedSubscriber,
            AcceptedTermsPermission,
        ]
        self.assertEqual(len(view.permission_classes), len(required_permissions))
        for permission in required_permissions:
            self.assertTrue(permission in view.permission_classes)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_get_model_id_when_undefined(self, *args):
        self.user.organization = Organization.objects.get_or_create(id=123)[0]
        mock_secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        self.client.force_authenticate(user=self.user)
        mock_secret_manager.get_secret.return_value = None

        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.get(reverse("wca_model_id"))
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
        self.user.organization = Organization.objects.get_or_create(id=123)[0]
        self.user.rh_user_has_seat = has_seat
        mock_secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        self.client.force_authenticate(user=self.user)
        date_time = timezone.now().isoformat()
        mock_secret_manager.get_secret.return_value = {
            "SecretString": "secret_model_id",
            "CreatedDate": date_time,
        }

        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.get(reverse("wca_model_id"))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            self.assertEqual(r.data["model_id"], "secret_model_id")
            self.assertEqual(r.data["last_update"], date_time)
            mock_secret_manager.get_secret.assert_called_with(123, Suffixes.MODEL_ID)
            self.assert_segment_log(log, "modelIdGet", None)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_get_model_id_when_defined_throws_exception(self, *args):
        self.user.organization = Organization.objects.get_or_create(id=123)[0]
        mock_secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        self.client.force_authenticate(user=self.user)
        mock_secret_manager.get_secret.side_effect = WcaSecretManagerError("Test")

        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.get(reverse("wca_model_id"))
            self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
            self.assertInLog("ansible_ai_connect.ai.api.aws.exceptions.WcaSecretManagerError", log)
            self.assert_segment_log(log, "modelIdGet", "WcaSecretManagerError")

    def test_set_model_id_authentication_error(self, *args):
        # self.client.force_authenticate(user=self.user)
        r = self.client.post(reverse("wca_model_id"))
        self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_set_key_without_org_id(self, *args):
        self.client.force_authenticate(user=self.user)

        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(reverse("wca_model_id"))
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            self.assert_segment_log(log, "modelIdSet", None)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_set_model_id(self, *args):
        self._test_set_model_id(False)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_set_model_id_seated_user(self, *args):
        self._test_set_model_id(True)

    def _test_set_model_id(self, has_seat):
        self.user.organization = Organization.objects.get_or_create(id=123)[0]
        self.user.rh_user_has_seat = has_seat
        mock_secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        self.client.force_authenticate(user=self.user)

        # ModelId should initially not exist
        mock_secret_manager.get_secret.return_value = None
        r = self.client.get(reverse("wca_model_id"))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        mock_secret_manager.get_secret.assert_called_with(123, Suffixes.MODEL_ID)

        # Set ModelId
        mock_secret_manager.get_secret.return_value = {"SecretString": "someAPIKey"}
        with self.assertLogs(logger="ansible_ai_connect.users.signals", level="DEBUG") as signals:
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(
                    reverse("wca_model_id"),
                    data='{ "model_id": "secret_model_id" }',
                    content_type="application/json",
                )

                self.assertEqual(r.status_code, HTTPStatus.NO_CONTENT)
                mock_secret_manager.save_secret.assert_called_with(
                    123, Suffixes.MODEL_ID, "secret_model_id"
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
        r = self.client.get(reverse("wca_model_id"))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertEqual(r.data["model_id"], "secret_model_id")
        mock_secret_manager.get_secret.assert_called_with(123, Suffixes.MODEL_ID)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_set_model_id_not_valid(self, *args):
        self.user.organization = Organization.objects.get_or_create(id=123)[0]
        mock_secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        mock_wca_client = apps.get_app_config("ai").model_mesh_client
        self.client.force_authenticate(user=self.user)

        # ModelId should initially not exist
        mock_secret_manager.get_secret.return_value = None

        r = self.client.get(reverse("wca_model_id"))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        mock_secret_manager.get_secret.assert_called_with(123, Suffixes.MODEL_ID)

        # Set ModelId
        mock_secret_manager.get_secret.return_value = {"SecretString": "someAPIKey"}

        with self.assertLogs(logger="root", level="DEBUG") as log:
            mock_wca_client.infer_from_parameters.side_effect = ValidationError
            r = self.client.post(
                reverse("wca_model_id"),
                data='{ "model_id": "secret_model_id" }',
                content_type="application/json",
            )
            mock_wca_client.infer_from_parameters.assert_called()
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            self.assertInLog("ValidationError", log)
            self.assert_segment_log(log, "modelIdSet", "ValidationError")

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_set_model_id_throws_secret_manager_exception(self, *args):
        self.user.organization = Organization.objects.get_or_create(id=123)[0]
        self.client.force_authenticate(user=self.user)
        mock_secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        mock_secret_manager.save_secret.side_effect = WcaSecretManagerError("Test")

        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(
                reverse("wca_model_id"),
                data='{ "model_id": "secret_model_id" }',
                content_type="application/json",
            )
            self.assertEqual(r.status_code, HTTPStatus.SERVICE_UNAVAILABLE)
            self.assertInLog("ansible_ai_connect.ai.api.aws.exceptions.WcaSecretManagerError", log)
            print(log)
            self.assert_segment_log(log, "modelIdSet", "WcaSecretManagerError")

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_set_model_id_throws_validation_exception(self, *args):
        self.user.organization = Organization.objects.get_or_create(id=123)[0]
        self.client.force_authenticate(user=self.user)
        mock_secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        mock_secret_manager.save_secret.side_effect = WcaSecretManagerError("Test")

        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(
                reverse("wca_model_id"),
                data='{ "unknown_json_field": "secret_model_id" }',
                content_type="application/json",
            )
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            self.assert_segment_log(log, "modelIdSet", "ValidationError")


@patch.object(IsOrganisationAdministrator, "has_permission", return_value=True)
@patch.object(IsOrganisationLightspeedSubscriber, "has_permission", return_value=False)
class TestWCAModelIdViewAsNonSubscriber(WisdomAppsBackendMocking, WisdomServiceAPITestCaseBase):
    def test_get_model_id_as_non_subscriber(self, *args):
        self.user.organization = Organization.objects.get_or_create(id=123)[0]
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse("wca_model_id"))
        self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)


@override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="wca")
@override_settings(WCA_SECRET_BACKEND_TYPE="aws_sm")
@patch.object(IsOrganisationAdministrator, "has_permission", return_value=True)
@patch.object(IsOrganisationLightspeedSubscriber, "has_permission", return_value=True)
class TestWCAModelIdValidatorView(
    WisdomAppsBackendMocking, WisdomServiceAPITestCaseBase, WisdomLogAwareMixin
):
    def setUp(self):
        super().setUp()
        self.secret_manager_patcher = patch.object(
            ansible_ai_connect.ai.apps, "AWSSecretManager", spec=AWSSecretManager
        )
        self.secret_manager_patcher.start()

        self.wca_client_patcher = patch.object(
            ansible_ai_connect.ai.apps, "WCAClient", spec=WCAClient
        )
        self.wca_client_patcher.start()
        apps.get_app_config("ai").ready()

    def tearDown(self):
        self.secret_manager_patcher.stop()
        self.wca_client_patcher.stop()
        super().tearDown()

    def test_validate(self, *args):
        self.user.organization = Organization.objects.get_or_create(id=123)[0]
        self.client.force_authenticate(user=self.user)
        mock_wca_client = apps.get_app_config("ai").model_mesh_client
        mock_wca_client.infer = Mock(return_value={})

        r = self.client.get(reverse("wca_model_id_validator"))
        self.assertEqual(r.status_code, HTTPStatus.OK)

    def test_validate_error_authentication(self, *args):
        # self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse("wca_model_id_validator"))
        self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_validate_error_no_org_id(self, *args):
        self.client.force_authenticate(user=self.user)

        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.get(reverse("wca_model_id_validator"))
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            self.assert_segment_log(log, "modelIdValidate", None)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_validate_error_no_api_key(self, *args):
        self.user.organization = Organization.objects.get_or_create(id=123)[0]
        mock_secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        self.client.force_authenticate(user=self.user)

        def mock_get_secret_no_api_key(*args, **kwargs):
            if args[1] == Suffixes.MODEL_ID:
                return {"SecretString": "some_model_id"}
            return {"SecretString": None}

        mock_secret_manager.get_secret.side_effect = mock_get_secret_no_api_key
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.get(reverse("wca_model_id_validator"))
            self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
            self.assertInLog(
                "ansible_ai_connect.ai.api.model_client.exceptions.WcaKeyNotFound", log
            )
            self.assert_segment_log(log, "modelIdValidate", "WcaKeyNotFound")

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_validate_error_no_model_id(self, *args):
        self.user.organization = Organization.objects.get_or_create(id=123)[0]
        mock_secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        self.client.force_authenticate(user=self.user)

        def mock_get_secret_no_model_id(*args, **kwargs):
            if args[1] == Suffixes.API_KEY:
                return {"SecretString": "some_api_key"}
            return {"SecretString": None}

        mock_secret_manager.get_secret.side_effect = mock_get_secret_no_model_id
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.get(reverse("wca_model_id_validator"))
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            self.assertInLog(
                "ansible_ai_connect.ai.api.model_client.exceptions.WcaModelIdNotFound", log
            )
            self.assert_segment_log(log, "modelIdValidate", "WcaModelIdNotFound")

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_validate_ok(self, *args):
        self._test_validate_ok(False)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_validate_ok_seated_user(self, *args):
        self._test_validate_ok(True)

    def _test_validate_ok(self, has_seat):
        self.user.organization = Organization.objects.get_or_create(id=123)[0]
        self.user.rh_user_has_seat = has_seat
        mock_secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        self.client.force_authenticate(user=self.user)

        def mock_get_secret_model_id(*args, **kwargs):
            if args[1] == Suffixes.API_KEY:
                return {"SecretString": "some_api_key"}
            return {"SecretString": "model_id"}

        mock_secret_manager.get_secret.side_effect = mock_get_secret_model_id

        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.get(reverse("wca_model_id_validator"))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            self.assert_segment_log(log, "modelIdValidate", None)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_validate_error_wrong_model_id(self, *args):
        self.user.organization = Organization.objects.get_or_create(id=123)[0]
        mock_wca_client = apps.get_app_config("ai").model_mesh_client
        self.client.force_authenticate(user=self.user)
        mock_wca_client.infer_from_parameters = Mock(side_effect=ValidationError)

        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.get(reverse("wca_model_id_validator"))
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            self.assertInLog("ValidationError", log)
            self.assert_segment_log(log, "modelIdValidate", "ValidationError")

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_validate_error_api_key_not_found(self, *args):
        self.user.organization = Organization.objects.get_or_create(id=123)[0]
        mock_wca_client = apps.get_app_config("ai").model_mesh_client
        self.client.force_authenticate(user=self.user)
        mock_wca_client.infer_from_parameters = Mock(side_effect=WcaKeyNotFound)

        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.get(reverse("wca_model_id_validator"))
            self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
            self.assertInLog(
                "ansible_ai_connect.ai.api.model_client.exceptions.WcaKeyNotFound", log
            )
            self.assert_segment_log(log, "modelIdValidate", "WcaKeyNotFound")

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_validate_error_user_trial_expired(self, *args):
        self.user.organization = Organization.objects.get_or_create(id=123)[0]
        mock_wca_client = apps.get_app_config("ai").model_mesh_client
        self.client.force_authenticate(user=self.user)
        mock_wca_client.infer_from_parameters = Mock(side_effect=WcaUserTrialExpired)

        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.get(reverse("wca_model_id_validator"))
            self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
            self.assertEqual(r.data["code"], "permission_denied__user_trial_expired")
            self.assertEqual(
                r.data["message"], "User trial expired. Please contact your administrator."
            )
            self.assertInLog(
                "ansible_ai_connect.ai.api.model_client.exceptions.WcaUserTrialExpired", log
            )
            self.assert_segment_log(log, "trialExpired", None, type="modelIdValidate")

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_validate_error_model_id_bad_request(self, *args):
        self.user.organization = Organization.objects.get_or_create(id=123)[0]
        mock_wca_client = apps.get_app_config("ai").model_mesh_client
        self.client.force_authenticate(user=self.user)
        mock_wca_client.infer_from_parameters = Mock(side_effect=WcaInvalidModelId)

        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.get(reverse("wca_model_id_validator"))
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            self.assertInLog(
                "ansible_ai_connect.ai.api.model_client.exceptions.WcaInvalidModelId", log
            )
            self.assert_segment_log(log, "modelIdValidate", "WcaInvalidModelId")

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_validate_error_model_id_exception(self, *args):
        self.user.organization = Organization.objects.get_or_create(id=123)[0]
        mock_wca_client = apps.get_app_config("ai").model_mesh_client
        self.client.force_authenticate(user=self.user)
        mock_wca_client.infer_from_parameters = Mock(side_effect=Exception)

        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.get(reverse("wca_model_id_validator"))
            self.assertEqual(r.status_code, HTTPStatus.SERVICE_UNAVAILABLE)
            self.assertInLog("Exception", log)
            self.assert_segment_log(log, "modelIdValidate", "Exception")
