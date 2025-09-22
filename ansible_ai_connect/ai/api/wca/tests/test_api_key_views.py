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
from typing import cast
from unittest import mock
from unittest.mock import MagicMock, Mock, patch

from django.apps import apps
from django.test import override_settings
from django.urls import resolve
from django.utils import timezone
from oauth2_provider.contrib.rest_framework import IsAuthenticatedOrTokenHasScope
from rest_framework.permissions import IsAuthenticated

import ansible_ai_connect.ai.apps
from ansible_ai_connect.ai.api.aws.exceptions import WcaSecretManagerError
from ansible_ai_connect.ai.api.aws.wca_secret_manager import AWSSecretManager, Suffixes
from ansible_ai_connect.ai.api.model_pipelines.exceptions import (
    WcaTokenFailure,
    WcaTokenFailureApiKeyError,
)
from ansible_ai_connect.ai.api.model_pipelines.pipelines import MetaData
from ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_saas import WCASaaSMetaData
from ansible_ai_connect.ai.api.permissions import (
    IsOrganisationAdministrator,
    IsOrganisationLightspeedSubscriber,
    IsWCASaaSModelPipeline,
)
from ansible_ai_connect.organizations.models import ExternalOrganization
from ansible_ai_connect.test_utils import (
    APIVersionTestCaseBase,
    WisdomAppsBackendMocking,
    WisdomServiceAPITestCaseBaseOIDC,
)


@override_settings(DEPLOYMENT_MODE="saas")
@override_settings(WCA_SECRET_BACKEND_TYPE="aws_sm")
@patch.object(IsOrganisationAdministrator, "has_permission", return_value=True)
@patch.object(IsOrganisationLightspeedSubscriber, "has_permission", return_value=True)
class TestWCAApiKeyView(
    APIVersionTestCaseBase, WisdomAppsBackendMocking, WisdomServiceAPITestCaseBaseOIDC
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

    def test_get_key_authentication_error(self, *args):
        # self.client.force_authenticate(user=self.user)
        r = self.client.get(self.api_version_reverse("wca_api_key"))
        self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_get_key_without_org_id(self, *args):
        self.user.organization = None
        self.client.force_authenticate(user=self.user)

        r = self.client.get(self.api_version_reverse("wca_api_key"))
        self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)

    def test_permission_classes(self, *args):
        url = self.api_version_reverse("wca_api_key")
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
    def test_get_key_when_undefined(self, *args):
        self.user.organization = ExternalOrganization.objects.get_or_create(id=123)[0]
        mock_secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        self.client.force_authenticate(user=self.user)
        mock_secret_manager.get_secret = Mock(return_value=None)

        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.get(self.api_version_reverse("wca_api_key"))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            mock_secret_manager.get_secret.assert_called_with(123, Suffixes.API_KEY)
            self.assert_segment_log(log, "modelApiKeyGet", None)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_get_key_when_defined(self, *args):
        self._test_get_key_when_defined(False)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_get_key_when_defined_seated_user(self, *args):
        self._test_get_key_when_defined(True)

    def _test_get_key_when_defined(self, has_seat):
        self.user.organization = ExternalOrganization.objects.get_or_create(id=123)[0]
        self.user.rh_user_has_seat = has_seat
        mock_secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        self.client.force_authenticate(user=self.user)
        date_time = timezone.now().isoformat()
        mock_secret_manager.get_secret = Mock(return_value={"CreatedDate": date_time})

        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.get(self.api_version_reverse("wca_api_key"))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            self.assertEqual(r.data["last_update"], date_time)
            mock_secret_manager.get_secret.assert_called_with(123, Suffixes.API_KEY)
            self.assert_segment_log(log, "modelApiKeyGet", None)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_get_key_when_defined_throws_exception(self, *args):
        self.user.organization = ExternalOrganization.objects.get_or_create(id=123)[0]
        mock_secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        self.client.force_authenticate(user=self.user)
        mock_secret_manager.get_secret.side_effect = WcaSecretManagerError("Test")

        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.get(self.api_version_reverse("wca_api_key"))
            self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
            self.assert_segment_log(log, "modelApiKeyGet", "WcaSecretManagerError")

    def test_set_key_authentication_error(self, *args):
        # self.client.force_authenticate(user=self.user)
        r = self.client.post(self.api_version_reverse("wca_api_key"))
        self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_set_key_without_org_id(self, *args):
        self.user.organization = None
        self.client.force_authenticate(user=self.user)

        r = self.client.post(self.api_version_reverse("wca_api_key"))
        self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_set_key_with_valid_value(self, *args):
        self._test_set_key_with_valid_value(False)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_set_key_with_valid_value_seated_user(self, *args):
        self._test_set_key_with_valid_value(True)

    def _test_set_key_with_valid_value(self, has_seat):
        self.user.organization = ExternalOrganization.objects.get_or_create(id=123)[0]
        self.user.rh_user_has_seat = has_seat
        _md = apps.get_app_config("ai").get_model_pipeline(MetaData)
        mock_model_meta_data: WCASaaSMetaData = cast(WCASaaSMetaData, _md)
        mock_secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        self.client.force_authenticate(user=self.user)

        # Key should initially not exist
        mock_secret_manager.get_secret = Mock(return_value=None)
        r = self.client.get(self.api_version_reverse("wca_api_key"))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        mock_secret_manager.get_secret.assert_called_with(123, Suffixes.API_KEY)

        # Set Key
        mock_model_meta_data.get_token = Mock(return_value="token")
        with self.assertLogs(logger="ansible_ai_connect.users.signals", level="DEBUG") as signals:
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.post(
                    self.api_version_reverse("wca_api_key"),
                    data='{ "key": "a-new-key" }',
                    content_type="application/json",
                )
                self.assertEqual(r.status_code, HTTPStatus.NO_CONTENT)
                mock_secret_manager.save_secret.assert_called_with(
                    123, Suffixes.API_KEY, "a-new-key"
                )
                self.assert_segment_log(log, "modelApiKeySet", None)

            # Check audit entry
            self.assertInLog(
                f"User: '{self.user}' set WCA Key for Organisation '{self.user.organization.id}'",
                signals,
            )

        # Check Key was stored
        mock_secret_manager.get_secret = Mock(
            return_value={"CreatedDate": timezone.now().isoformat()}
        )
        r = self.client.get(self.api_version_reverse("wca_api_key"))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        mock_secret_manager.get_secret.assert_called_with(123, Suffixes.API_KEY)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_set_key_with_invalid_value(self, *args):
        self.user.organization = ExternalOrganization.objects.get_or_create(id=123)[0]
        _md = apps.get_app_config("ai").get_model_pipeline(MetaData)
        mock_model_meta_data: WCASaaSMetaData = cast(WCASaaSMetaData, _md)
        mock_secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        self.client.force_authenticate(user=self.user)

        # Key should initially not exist
        mock_secret_manager.get_secret = Mock(return_value=None)
        r = self.client.get(self.api_version_reverse("wca_api_key"))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        mock_secret_manager.get_secret.assert_called_with(123, Suffixes.API_KEY)

        # Set Key
        mock_model_meta_data.get_token = Mock(
            side_effect=WcaTokenFailureApiKeyError("Something went wrong")
        )
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(
                self.api_version_reverse("wca_api_key"),
                data='{ "key": "a-new-key" }',
                content_type="application/json",
            )
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            mock_secret_manager.save_secret.assert_not_called()
            self.assert_segment_log(log, "modelApiKeySet", "WcaTokenFailureApiKeyError")

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_set_key_throws_secret_manager_exception(self, *args):
        self.user.organization = ExternalOrganization.objects.get_or_create(id=123)[0]
        mock_secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        _md = apps.get_app_config("ai").get_model_pipeline(MetaData)
        mock_model_meta_data: WCASaaSMetaData = cast(WCASaaSMetaData, _md)
        self.client.force_authenticate(user=self.user)
        mock_model_meta_data.get_token = Mock(return_value="token")
        mock_secret_manager.save_secret.side_effect = WcaSecretManagerError("Test")

        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(
                self.api_version_reverse("wca_api_key"),
                data='{ "key": "a-new-key" }',
                content_type="application/json",
            )
            self.assertEqual(r.status_code, HTTPStatus.SERVICE_UNAVAILABLE)
            self.assert_segment_log(log, "modelApiKeySet", "WcaSecretManagerError")

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_set_key_throws_http_exception(self, *args):
        self.user.organization = ExternalOrganization.objects.get_or_create(id=123)[0]
        _md = apps.get_app_config("ai").get_model_pipeline(MetaData)
        mock_model_meta_data: WCASaaSMetaData = cast(WCASaaSMetaData, _md)
        self.client.force_authenticate(user=self.user)
        mock_model_meta_data.get_token = Mock(side_effect=WcaTokenFailure())
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(
                self.api_version_reverse("wca_api_key"),
                data='{ "key": "a-new-key" }',
                content_type="application/json",
            )
            self.assertEqual(r.status_code, HTTPStatus.SERVICE_UNAVAILABLE)
            self.assert_segment_log(log, "modelApiKeySet", "WcaTokenFailure")

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_set_key_throws_validation_exception(self, *args):
        self.user.organization = ExternalOrganization.objects.get_or_create(id=123)[0]
        self.client.force_authenticate(user=self.user)

        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.post(
                self.api_version_reverse("wca_api_key"),
                data='{ "unknown_json_field": "a-new-key" }',
                content_type="application/json",
            )
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            self.assert_segment_log(log, "modelApiKeySet", "ValidationError")

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_delete_key_without_org_id(self, *args):
        self.user.organization = None
        self.client.force_authenticate(user=self.user)

        r = self.client.delete(self.api_version_reverse("wca_api_key"))
        self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_delete_key(self, *args):
        self.user.organization = ExternalOrganization.objects.get_or_create(id=123)[0]
        _md = apps.get_app_config("ai").get_model_pipeline(MetaData)
        mock_model_meta_data: WCASaaSMetaData = cast(WCASaaSMetaData, _md)
        mock_secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        self.client.force_authenticate(user=self.user)

        secrets = {
            Suffixes.API_KEY: {"CreatedDate": timezone.now().isoformat()},
            Suffixes.MODEL_ID: {"CreatedDate": timezone.now().isoformat()},
        }

        def get_secret(*args, **kwargs):
            if args == (self.user.organization.id, Suffixes.API_KEY):
                return secrets.get(Suffixes.API_KEY, None)
            elif args == (self.user.organization.id, Suffixes.MODEL_ID):
                return secrets.get(Suffixes.MODEL_ID, None)
            else:
                return Exception("exception occurred")

        def delete_secret(*args, **kwargs):
            if args == (self.user.organization.id, Suffixes.API_KEY):
                return secrets.pop(Suffixes.API_KEY)
            elif args == (self.user.organization.id, Suffixes.MODEL_ID):
                return secrets.pop(Suffixes.MODEL_ID)
            else:
                return Exception("exception occurred")

        mock_secret_manager.get_secret = MagicMock(side_effect=get_secret)
        mock_secret_manager.delete_secret = MagicMock(side_effect=delete_secret)

        r = self.client.get(self.api_version_reverse("wca_api_key"))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        mock_secret_manager.get_secret.assert_called_with(
            self.user.organization.id, Suffixes.API_KEY
        )

        # Delete key and model id
        mock_model_meta_data.get_token.return_value = "token"
        with self.assertLogs(logger="ansible_ai_connect.users.signals", level="DEBUG") as signals:
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.delete(self.api_version_reverse("wca_api_key"))
                self.assertEqual(r.status_code, HTTPStatus.NO_CONTENT)
                mock_secret_manager.delete_secret.assert_has_calls(
                    [
                        mock.call(self.user.organization.id, Suffixes.API_KEY),
                        mock.call(self.user.organization.id, Suffixes.MODEL_ID),
                    ]
                )
                self.assert_segment_log(log, "modelApiKeyDelete", None)

            # Check audit entries
            self.assertInLog(
                f"User: '{self.user}' delete WCA Key for Organization "
                f"'{self.user.organization.id}'",
                signals,
            )
            self.assertInLog(
                f"User: '{self.user}' delete WCA Model Id for Organization "
                f"'{self.user.organization.id}'",
                signals,
            )

        # Check Key was deleted
        mock_secret_manager.get_secret.return_value = None
        r = self.client.get(self.api_version_reverse("wca_api_key"))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        mock_secret_manager.get_secret.assert_called_with(
            self.user.organization.id, Suffixes.API_KEY
        )

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_delete_key_with_model_id_deletion_error(self, *args):
        self.user.organization = ExternalOrganization.objects.get_or_create(id=123)[0]
        _md = apps.get_app_config("ai").get_model_pipeline(MetaData)
        mock_model_meta_data: WCASaaSMetaData = cast(WCASaaSMetaData, _md)
        mock_secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        self.client.force_authenticate(user=self.user)

        secrets = {
            Suffixes.API_KEY: {"CreatedDate": timezone.now().isoformat()},
            Suffixes.MODEL_ID: {"CreatedDate": timezone.now().isoformat()},
        }

        def get_secret(*args, **kwargs):
            if args == (self.user.organization.id, Suffixes.API_KEY):
                return secrets.get(Suffixes.API_KEY, None)
            elif args == (self.user.organization.id, Suffixes.MODEL_ID):
                return secrets.get(Suffixes.MODEL_ID, None)
            else:
                return Exception("exception occurred")

        def delete_secret(*args, **kwargs):
            if args == (self.user.organization.id, Suffixes.API_KEY):
                return secrets.pop(Suffixes.API_KEY)
            elif args == (self.user.organization.id, Suffixes.MODEL_ID):
                raise Exception("exception occurred")
            else:
                return Exception("exception occurred")

        mock_secret_manager.get_secret = MagicMock(side_effect=get_secret)
        mock_secret_manager.delete_secret = MagicMock(side_effect=delete_secret)

        r = self.client.get(self.api_version_reverse("wca_api_key"))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        mock_secret_manager.get_secret.assert_called_with(
            self.user.organization.id, Suffixes.API_KEY
        )

        # Delete key and model id
        mock_model_meta_data.get_token.return_value = "token"
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.delete(self.api_version_reverse("wca_api_key"))
            self.assertEqual(r.status_code, HTTPStatus.SERVICE_UNAVAILABLE)
            mock_secret_manager.delete_secret.assert_has_calls(
                [
                    mock.call(self.user.organization.id, Suffixes.MODEL_ID),
                ]
            )
            self.assert_segment_log(log, "modelApiKeyDelete", None)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_delete_key_with_api_key_deletion_error(self, *args):
        self.user.organization = ExternalOrganization.objects.get_or_create(id=123)[0]
        _md = apps.get_app_config("ai").get_model_pipeline(MetaData)
        mock_model_meta_data: WCASaaSMetaData = cast(WCASaaSMetaData, _md)
        mock_secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        self.client.force_authenticate(user=self.user)

        secrets = {
            Suffixes.API_KEY: {"CreatedDate": timezone.now().isoformat()},
            Suffixes.MODEL_ID: {"CreatedDate": timezone.now().isoformat()},
        }

        def get_secret(*args, **kwargs):
            if args == (self.user.organization.id, Suffixes.API_KEY):
                return secrets.get(Suffixes.API_KEY, None)
            elif args == (self.user.organization.id, Suffixes.MODEL_ID):
                return secrets.get(Suffixes.MODEL_ID, None)
            else:
                return Exception("exception occurred")

        def delete_secret(*args, **kwargs):
            if args == (self.user.organization.id, Suffixes.API_KEY):
                raise Exception("exception occurred")
            elif args == (self.user.organization.id, Suffixes.MODEL_ID):
                return secrets.pop(Suffixes.MODEL_ID)
            else:
                return Exception("exception occurred")

        mock_secret_manager.get_secret = MagicMock(side_effect=get_secret)
        mock_secret_manager.delete_secret = MagicMock(side_effect=delete_secret)

        r = self.client.get(self.api_version_reverse("wca_api_key"))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        mock_secret_manager.get_secret.assert_called_with(
            self.user.organization.id, Suffixes.API_KEY
        )

        # Delete key and model id
        mock_model_meta_data.get_token.return_value = "token"
        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.delete(self.api_version_reverse("wca_api_key"))
            self.assertEqual(r.status_code, HTTPStatus.SERVICE_UNAVAILABLE)
            mock_secret_manager.delete_secret.assert_has_calls(
                [
                    mock.call(self.user.organization.id, Suffixes.API_KEY),
                ]
            )
            self.assert_segment_log(log, "modelApiKeyDelete", None)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_delete_key_with_no_model_id(self, *args):
        self.user.organization = ExternalOrganization.objects.get_or_create(id=123)[0]
        _md = apps.get_app_config("ai").get_model_pipeline(MetaData)
        mock_model_meta_data: WCASaaSMetaData = cast(WCASaaSMetaData, _md)
        mock_secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        self.client.force_authenticate(user=self.user)

        def get_secret(*args, **kwargs):
            if args == (self.user.organization.id, Suffixes.API_KEY):
                return {"CreatedDate": timezone.now().isoformat()}
            elif args == (self.user.organization.id, Suffixes.MODEL_ID):
                return None
            else:
                return Exception("exception occurred")

        mock_secret_manager.get_secret = MagicMock(side_effect=get_secret)
        r = self.client.get(self.api_version_reverse("wca_api_key"))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        mock_secret_manager.get_secret.assert_called_with(
            self.user.organization.id, Suffixes.API_KEY
        )

        # Delete key and model id
        mock_model_meta_data.get_token.return_value = "token"
        with self.assertLogs(logger="ansible_ai_connect.users.signals", level="DEBUG") as signals:
            with self.assertLogs(logger="root", level="DEBUG") as log:
                r = self.client.delete(self.api_version_reverse("wca_api_key"))
                self.assertEqual(r.status_code, HTTPStatus.NO_CONTENT)
                mock_secret_manager.delete_secret.assert_has_calls(
                    [mock.call(self.user.organization.id, Suffixes.API_KEY)]
                )
                self.assert_segment_log(log, "modelApiKeyDelete", None)

            # Check audit entries
            self.assertInLog(
                f"User: '{self.user}' delete WCA Key for Organization "
                f"'{self.user.organization.id}'",
                signals,
            )

        # Check Key was deleted
        mock_secret_manager.get_secret.return_value = None
        r = self.client.get(self.api_version_reverse("wca_api_key"))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        mock_secret_manager.get_secret.assert_called_with(
            self.user.organization.id, Suffixes.API_KEY
        )

    def test_delete_key_with_no_key_no_model_id(self, *args):
        self.user.organization = ExternalOrganization.objects.get_or_create(id=123)[0]
        mock_secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        self.client.force_authenticate(user=self.user)

        def get_secret(*args, **kwargs):
            if args == (self.user.organization.id, Suffixes.API_KEY):
                return None
            elif args == (self.user.organization.id, Suffixes.MODEL_ID):
                return None
            else:
                return Exception("exception occurred")

        mock_secret_manager.get_secret = MagicMock(side_effect=get_secret)
        r = self.client.delete(self.api_version_reverse("wca_api_key"))
        self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)

        mock_secret_manager.get_secret.assert_called_with(
            self.user.organization.id, Suffixes.API_KEY
        )
        mock_secret_manager.delete_secret.assert_not_called()


@patch.object(IsOrganisationAdministrator, "has_permission", return_value=True)
@patch.object(IsOrganisationLightspeedSubscriber, "has_permission", return_value=False)
class TestWCAApiKeyViewAsNonSubscriber(APIVersionTestCaseBase, WisdomServiceAPITestCaseBaseOIDC):
    def test_get_api_key_as_non_subscriber(self, *args):
        self.user.organization = ExternalOrganization.objects.get_or_create(id=123)[0]
        self.client.force_authenticate(user=self.user)
        r = self.client.get(self.api_version_reverse("wca_api_key"))
        self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)


@override_settings(DEPLOYMENT_MODE="saas")
@override_settings(WCA_SECRET_BACKEND_TYPE="aws_sm")
@patch.object(IsOrganisationAdministrator, "has_permission", return_value=True)
@patch.object(IsOrganisationLightspeedSubscriber, "has_permission", return_value=True)
class TestWCAApiKeyValidatorView(
    APIVersionTestCaseBase, WisdomAppsBackendMocking, WisdomServiceAPITestCaseBaseOIDC
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

    def test_validate_key_authentication_error(self, *args):
        # self.client.force_authenticate(user=self.user)
        r = self.client.get(self.api_version_reverse("wca_api_key_validator"))
        self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_validate_key_without_org_id(self, *args):
        self.user.organization = None
        self.client.force_authenticate(user=self.user)

        r = self.client.get(self.api_version_reverse("wca_api_key_validator"))
        self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_validate_key_with_valid_value(self, *args):
        self._test_validate_key_with_valid_value(False)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_validate_key_with_valid_value_seated_user(self, *args):
        self._test_validate_key_with_valid_value(True)

    def _test_validate_key_with_valid_value(self, has_seat):
        self.user.organization = ExternalOrganization.objects.get_or_create(id=123)[0]
        self.user.rh_user_has_seat = has_seat
        mock_secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        _md = apps.get_app_config("ai").get_model_pipeline(MetaData)
        mock_model_meta_data: WCASaaSMetaData = cast(WCASaaSMetaData, _md)
        self.client.force_authenticate(user=self.user)

        mock_model_meta_data.get_token = Mock(return_value="token")
        mock_secret_manager.get_secret = Mock(return_value={"SecretString": "wca_key"})

        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.get(self.api_version_reverse("wca_api_key_validator"))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            self.assert_segment_log(log, "modelApiKeyValidate", None)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_validate_key_with_missing_value(self, *args):
        self.user.organization = ExternalOrganization.objects.get_or_create(id=123)[0]
        mock_secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        self.client.force_authenticate(user=self.user)
        mock_secret_manager.get_secret = Mock(return_value=None)

        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.get(self.api_version_reverse("wca_api_key_validator"))
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            self.assert_segment_log(log, "modelApiKeyValidate", None)

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_validate_key_with_invalid_value(self, *args):
        self.user.organization = ExternalOrganization.objects.get_or_create(id=123)[0]
        _md = apps.get_app_config("ai").get_model_pipeline(MetaData)
        mock_model_meta_data: WCASaaSMetaData = cast(WCASaaSMetaData, _md)
        self.client.force_authenticate(user=self.user)
        mock_model_meta_data.get_token = Mock(
            side_effect=WcaTokenFailureApiKeyError("Something went wrong")
        )

        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.get(self.api_version_reverse("wca_api_key_validator"))
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            self.assert_segment_log(log, "modelApiKeyValidate", "WcaTokenFailureApiKeyError")

    @override_settings(SEGMENT_WRITE_KEY="DUMMY_KEY_VALUE")
    def test_validate_key_throws_http_exception(self, *args):
        self.user.organization = ExternalOrganization.objects.get_or_create(id=123)[0]
        _md = apps.get_app_config("ai").get_model_pipeline(MetaData)
        mock_model_meta_data: WCASaaSMetaData = cast(WCASaaSMetaData, _md)
        self.client.force_authenticate(user=self.user)
        mock_model_meta_data.get_token = Mock(side_effect=WcaTokenFailure("Something went wrong"))

        with self.assertLogs(logger="root", level="DEBUG") as log:
            r = self.client.get(self.api_version_reverse("wca_api_key_validator"))
            self.assertEqual(r.status_code, HTTPStatus.SERVICE_UNAVAILABLE)
            self.assert_segment_log(log, "modelApiKeyValidate", "WcaTokenFailure")
