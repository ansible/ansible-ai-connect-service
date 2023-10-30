from http import HTTPStatus
from typing import Union
from unittest.mock import Mock, patch

from ai.api.aws.exceptions import WcaSecretManagerError
from ai.api.aws.wca_secret_manager import Suffixes, WcaSecretManager
from ai.api.model_client.wca_client import WcaBadRequest, WCAClient, WcaKeyNotFound
from ai.api.permissions import (
    AcceptedTermsPermission,
    IsOrganisationAdministrator,
    IsOrganisationLightspeedSubscriber,
)
from ai.api.tests.test_views import WisdomServiceAPITestCaseBase
from django.apps import apps
from django.test import override_settings
from django.urls import resolve, reverse
from django.utils import timezone
from oauth2_provider.contrib.rest_framework import IsAuthenticatedOrTokenHasScope
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from test_utils import WisdomLogAwareMixin


def _assert_segment_log(test, log, event: str, problem: Union[str | None]):
    segment_events = test.extractSegmentEventsFromLog(log)
    test.assertTrue(len(segment_events) == 1)
    test.assertEqual(segment_events[0]["event"], event)
    test.assertEqual(segment_events[0]["properties"]["problem"], problem)
    test.assertEqual(segment_events[0]["properties"]["exception"], True if problem else False)


@patch.object(IsOrganisationAdministrator, 'has_permission', return_value=True)
@patch.object(IsOrganisationLightspeedSubscriber, 'has_permission', return_value=True)
class TestWCAModelIdView(WisdomServiceAPITestCaseBase, WisdomLogAwareMixin):
    def setUp(self):
        super().setUp()
        self.secret_manager_patcher = patch.object(
            apps.get_app_config('ai'), '_wca_secret_manager', spec=WcaSecretManager
        )
        self.mock_secret_manager = self.secret_manager_patcher.start()

        self.wca_client_patcher = patch.object(
            apps.get_app_config('ai'), 'wca_client', spec=WCAClient
        )
        self.mock_wca_client = self.wca_client_patcher.start()

    def tearDown(self):
        self.secret_manager_patcher.stop()
        self.wca_client_patcher.stop()

    def test_get_model_id_authentication_error(self, *args):
        # self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('wca_model_id'))
        self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_get_key_without_org_id(self, *args):
        self.client.force_authenticate(user=self.user)

        with self.assertLogs(logger='root', level='DEBUG') as log:
            r = self.client.get(reverse('wca_model_id'))
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            _assert_segment_log(self, log, "modelIdGet", None)

    def test_permission_classes(self, *args):
        url = reverse('wca_model_id')
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

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_get_model_id_when_undefined(self, *args):
        self.user.organization_id = '123'
        self.client.force_authenticate(user=self.user)
        self.mock_secret_manager.get_secret.return_value = None

        with self.assertLogs(logger='root', level='DEBUG') as log:
            r = self.client.get(reverse('wca_model_id'))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            self.mock_secret_manager.get_secret.assert_called_with('123', Suffixes.MODEL_ID)
            _assert_segment_log(self, log, "modelIdGet", None)

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_get_model_id_when_defined(self, *args):
        self._test_get_model_id_when_defined(False)

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_get_model_id_when_defined_seated_user(self, *args):
        self._test_get_model_id_when_defined(True)

    def _test_get_model_id_when_defined(self, has_seat):
        self.user.organization_id = '123'
        self.user.rh_user_has_seat = has_seat
        self.client.force_authenticate(user=self.user)
        date_time = timezone.now().isoformat()
        self.mock_secret_manager.get_secret.return_value = {
            'SecretString': 'secret_model_id',
            'CreatedDate': date_time,
        }

        with self.assertLogs(logger='root', level='DEBUG') as log:
            r = self.client.get(reverse('wca_model_id'))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            self.assertEqual(r.data['model_id'], 'secret_model_id')
            self.assertEqual(r.data['last_update'], date_time)
            self.mock_secret_manager.get_secret.assert_called_with('123', Suffixes.MODEL_ID)
            _assert_segment_log(self, log, "modelIdGet", None)

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_get_model_id_when_defined_throws_exception(self, *args):
        self.user.organization_id = '123'
        self.client.force_authenticate(user=self.user)
        self.mock_secret_manager.get_secret.side_effect = WcaSecretManagerError('Test')

        with self.assertLogs(logger='root', level='DEBUG') as log:
            r = self.client.get(reverse('wca_model_id'))
            self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
            self.assertInLog('ai.api.aws.exceptions.WcaSecretManagerError', log)
            _assert_segment_log(self, log, "modelIdGet", "WcaSecretManagerError")

    def test_set_model_id_authentication_error(self, *args):
        # self.client.force_authenticate(user=self.user)
        r = self.client.post(reverse('wca_model_id'))
        self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_set_key_without_org_id(self, *args):
        self.client.force_authenticate(user=self.user)

        with self.assertLogs(logger='root', level='DEBUG') as log:
            r = self.client.post(reverse('wca_model_id'))
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            _assert_segment_log(self, log, "modelIdSet", None)

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_set_model_id(self, *args):
        self._test_set_model_id(False)

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_set_model_id_seated_user(self, *args):
        self._test_set_model_id(True)

    def _test_set_model_id(self, has_seat):
        self.user.organization_id = '123'
        self.user.rh_user_has_seat = has_seat
        self.client.force_authenticate(user=self.user)

        # ModelId should initially not exist
        self.mock_secret_manager.get_secret.return_value = None
        r = self.client.get(reverse('wca_model_id'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.mock_secret_manager.get_secret.assert_called_with('123', Suffixes.MODEL_ID)

        # Set ModelId
        self.mock_secret_manager.get_secret.return_value = {'SecretString': 'someAPIKey'}
        with self.assertLogs(logger='users.signals', level='DEBUG') as signals:
            with self.assertLogs(logger='root', level='DEBUG') as log:
                r = self.client.post(
                    reverse('wca_model_id'),
                    data='{ "model_id": "secret_model_id" }',
                    content_type='application/json',
                )

                self.assertEqual(r.status_code, HTTPStatus.NO_CONTENT)
                self.mock_secret_manager.save_secret.assert_called_with(
                    '123', Suffixes.MODEL_ID, 'secret_model_id'
                )
                _assert_segment_log(self, log, "modelIdSet", None)

            # Check audit entry
            self.assertInLog(
                f"User: '{self.user}' set WCA Model Id for "
                f"Organisation '{self.user.organization_id}'",
                signals,
            )

        # Check ModelId was stored
        self.mock_secret_manager.get_secret.return_value = {
            'SecretString': 'secret_model_id',
            'CreatedDate': timezone.now().isoformat(),
        }
        r = self.client.get(reverse('wca_model_id'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertEqual(r.data['model_id'], 'secret_model_id')
        self.mock_secret_manager.get_secret.assert_called_with('123', Suffixes.MODEL_ID)

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_set_model_id_not_valid(self, *args):
        self.user.organization_id = '123'
        self.client.force_authenticate(user=self.user)

        # ModelId should initially not exist
        self.mock_secret_manager.get_secret.return_value = None

        r = self.client.get(reverse('wca_model_id'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.mock_secret_manager.get_secret.assert_called_with('123', Suffixes.MODEL_ID)

        # Set ModelId
        self.mock_secret_manager.get_secret.return_value = {'SecretString': 'someAPIKey'}

        with self.assertLogs(logger='root', level='DEBUG') as log:
            self.mock_wca_client.infer_from_parameters.side_effect = ValidationError
            r = self.client.post(
                reverse('wca_model_id'),
                data='{ "model_id": "secret_model_id" }',
                content_type='application/json',
            )
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            self.assertInLog("ValidationError", log)
            _assert_segment_log(self, log, "modelIdSet", "ValidationError")

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_set_model_id_throws_secret_manager_exception(self, *args):
        self.user.organization_id = '123'
        self.client.force_authenticate(user=self.user)
        self.mock_secret_manager.save_secret.side_effect = WcaSecretManagerError('Test')

        with self.assertLogs(logger='root', level='DEBUG') as log:
            r = self.client.post(
                reverse('wca_model_id'),
                data='{ "model_id": "secret_model_id" }',
                content_type='application/json',
            )
            self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
            self.assertInLog('ai.api.aws.exceptions.WcaSecretManagerError', log)
            _assert_segment_log(self, log, "modelIdSet", "WcaSecretManagerError")

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_set_model_id_throws_validation_exception(self, *args):
        self.user.organization_id = '123'
        self.client.force_authenticate(user=self.user)
        self.mock_secret_manager.save_secret.side_effect = WcaSecretManagerError('Test')

        with self.assertLogs(logger='root', level='DEBUG') as log:
            r = self.client.post(
                reverse('wca_model_id'),
                data='{ "unknown_json_field": "secret_model_id" }',
                content_type='application/json',
            )
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            _assert_segment_log(self, log, "modelIdSet", "ValidationError")


@patch.object(IsOrganisationAdministrator, 'has_permission', return_value=True)
@patch.object(IsOrganisationLightspeedSubscriber, 'has_permission', return_value=False)
class TestWCAModelIdViewAsNonSubscriber(WisdomServiceAPITestCaseBase):
    def test_get_model_id_as_non_subscriber(self, *args):
        self.user.organization_id = '123'
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('wca_model_id'))
        self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)


@patch.object(IsOrganisationAdministrator, 'has_permission', return_value=True)
@patch.object(IsOrganisationLightspeedSubscriber, 'has_permission', return_value=True)
class TestWCAModelIdValidatorView(WisdomServiceAPITestCaseBase, WisdomLogAwareMixin):
    def setUp(self):
        super().setUp()
        self.secret_manager_patcher = patch.object(
            apps.get_app_config('ai'), '_wca_secret_manager', spec=WcaSecretManager
        )
        self.mock_secret_manager = self.secret_manager_patcher.start()
        self.wca_client_patcher = patch.object(
            apps.get_app_config('ai'), 'wca_client', spec=WCAClient
        )
        self.mock_wca_client = self.wca_client_patcher.start()

    def test_validate(self, *args):
        self.user.organization_id = '123'
        self.client.force_authenticate(user=self.user)
        self.mock_wca_client.infer = Mock(return_value={})

        r = self.client.get(reverse('wca_model_id_validator'))
        self.assertEqual(r.status_code, HTTPStatus.OK)

    def test_validate_error_authentication(self, *args):
        # self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('wca_model_id_validator'))
        self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_validate_error_no_org_id(self, *args):
        self.client.force_authenticate(user=self.user)

        with self.assertLogs(logger='root', level='DEBUG') as log:
            r = self.client.get(reverse('wca_model_id_validator'))
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            _assert_segment_log(self, log, "modelIdValidate", None)

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_validate_error_no_api_key(self, *args):
        self.user.organization_id = '123'
        self.client.force_authenticate(user=self.user)

        def mock_get_secret_no_api_key(*args, **kwargs):
            if args[1] == Suffixes.MODEL_ID:
                return {'SecretString': 'some_model_id'}
            return {'SecretString': None}

        self.mock_secret_manager.get_secret.side_effect = mock_get_secret_no_api_key
        with self.assertLogs(logger='root', level='DEBUG') as log:
            r = self.client.get(reverse('wca_model_id_validator'))
            self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
            self.assertInLog("ai.api.model_client.exceptions.WcaKeyNotFound", log)
            _assert_segment_log(self, log, "modelIdValidate", "WcaKeyNotFound")

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_validate_error_no_model_id(self, *args):
        self.user.organization_id = '123'
        self.client.force_authenticate(user=self.user)

        def mock_get_secret_no_model_id(*args, **kwargs):
            if args[1] == Suffixes.API_KEY:
                return {'SecretString': 'some_api_key'}
            return {'SecretString': None}

        self.mock_secret_manager.get_secret.side_effect = mock_get_secret_no_model_id
        with self.assertLogs(logger='root', level='DEBUG') as log:
            r = self.client.get(reverse('wca_model_id_validator'))
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            self.assertInLog("ai.api.model_client.exceptions.WcaModelIdNotFound", log)
            _assert_segment_log(self, log, "modelIdValidate", "WcaModelIdNotFound")

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_validate_ok(self, *args):
        self._test_validate_ok(False)

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_validate_ok_seated_user(self, *args):
        self._test_validate_ok(True)

    def _test_validate_ok(self, has_seat):
        self.user.organization_id = '123'
        self.user.rh_user_has_seat = has_seat
        self.client.force_authenticate(user=self.user)

        def mock_get_secret_model_id(*args, **kwargs):
            if args[1] == Suffixes.API_KEY:
                return {'SecretString': 'some_api_key'}
            return {'SecretString': 'model_id'}

        self.mock_secret_manager.get_secret.side_effect = mock_get_secret_model_id

        with self.assertLogs(logger='root', level='DEBUG') as log:
            r = self.client.get(reverse('wca_model_id_validator'))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            _assert_segment_log(self, log, "modelIdValidate", None)

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_validate_error_wrong_model_id(self, *args):
        self.user.organization_id = '123'
        self.client.force_authenticate(user=self.user)
        self.mock_wca_client.infer_from_parameters = Mock(side_effect=ValidationError)

        with self.assertLogs(logger='root', level='DEBUG') as log:
            r = self.client.get(reverse('wca_model_id_validator'))
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            self.assertInLog("ValidationError", log)
            _assert_segment_log(self, log, "modelIdValidate", "ValidationError")

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_validate_error_api_key_not_found(self, *args):
        self.user.organization_id = '123'
        self.client.force_authenticate(user=self.user)
        self.mock_wca_client.infer_from_parameters = Mock(side_effect=WcaKeyNotFound)

        with self.assertLogs(logger='root', level='DEBUG') as log:
            r = self.client.get(reverse('wca_model_id_validator'))
            self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
            self.assertInLog("ai.api.model_client.exceptions.WcaKeyNotFound", log)
            _assert_segment_log(self, log, "modelIdValidate", "WcaKeyNotFound")

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_validate_error_model_id_bad_request(self, *args):
        self.user.organization_id = '123'
        self.client.force_authenticate(user=self.user)
        self.mock_wca_client.infer_from_parameters = Mock(side_effect=WcaBadRequest)

        with self.assertLogs(logger='root', level='DEBUG') as log:
            r = self.client.get(reverse('wca_model_id_validator'))
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
            self.assertInLog("ai.api.model_client.exceptions.WcaBadRequest", log)
            _assert_segment_log(self, log, "modelIdValidate", "WcaBadRequest")

    @override_settings(SEGMENT_WRITE_KEY='DUMMY_KEY_VALUE')
    def test_validate_error_model_id_exception(self, *args):
        self.user.organization_id = '123'
        self.client.force_authenticate(user=self.user)
        self.mock_wca_client.infer_from_parameters = Mock(side_effect=Exception)

        with self.assertLogs(logger='root', level='DEBUG') as log:
            r = self.client.get(reverse('wca_model_id_validator'))
            self.assertEqual(r.status_code, HTTPStatus.SERVICE_UNAVAILABLE)
            self.assertInLog("Exception", log)
            _assert_segment_log(self, log, "modelIdValidate", "Exception")
