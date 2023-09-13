from http import HTTPStatus
from unittest import mock
from unittest.mock import patch

from ai.api.aws.exceptions import WcaSecretManagerError
from ai.api.aws.wca_secret_manager import Suffixes, WcaSecretManager
from ai.api.permissions import (
    AcceptedTermsPermission,
    IsOrganisationAdministrator,
    IsOrganisationLightspeedSubscriber,
    IsWCAModelIdApiFeatureFlagOn,
)
from ai.api.tests.test_views import WisdomServiceAPITestCaseBase
from django.apps import apps
from django.test import override_settings
from django.urls import resolve, reverse
from django.utils import timezone
from oauth2_provider.contrib.rest_framework import IsAuthenticatedOrTokenHasScope
from rest_framework.permissions import IsAuthenticated


@patch.object(IsOrganisationAdministrator, 'has_permission', return_value=True)
@patch.object(IsOrganisationLightspeedSubscriber, 'has_permission', return_value=True)
class TestWCAModelIdFeatureFlagView(WisdomServiceAPITestCaseBase):
    def setUp(self):
        super().setUp()
        self.secret_manager_patcher = patch.object(
            apps.get_app_config('ai'), '_wca_secret_manager', spec=WcaSecretManager
        )
        self.mock_secret_manager = self.secret_manager_patcher.start()

    def tearDown(self):
        self.secret_manager_patcher.stop()

    @override_settings(LAUNCHDARKLY_SDK_KEY=None)
    def test_featureflag_disabled(self, *args):
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('wca_model_id'))
        self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
        r = self.client.post(reverse('wca_model_id'))
        self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)

    @override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
    @mock.patch('ai.api.permissions.feature_flags')
    def test_featureflag_on_get_model_id(self, feature_flags, *args):
        def get_feature_flags(name, *args):
            return "true"

        feature_flags.get = get_feature_flags
        self.user.organization_id = "1"
        self.client.force_authenticate(user=self.user)
        self.mock_secret_manager.get_secret.return_value = {'SecretString': '1', 'CreatedDate': '0'}
        r = self.client.get(reverse('wca_model_id'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.mock_secret_manager.get_secret.assert_called_once_with('1', Suffixes.MODEL_ID)

    @override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
    @mock.patch('ai.api.permissions.feature_flags')
    def test_featureflag_on_set_model_id(self, feature_flags, *args):
        def get_feature_flags(name, *args):
            return "true"

        feature_flags.get = get_feature_flags
        self.user.organization_id = "1"
        self.client.force_authenticate(user=self.user)
        r = self.client.post(
            reverse('wca_model_id'),
            data='{ "model_id": "secret_model_id" }',
            content_type='application/json',
        )
        self.assertEqual(r.status_code, HTTPStatus.NO_CONTENT)
        self.mock_secret_manager.save_secret.assert_called_once_with(
            '1', Suffixes.MODEL_ID, 'secret_model_id'
        )

    @override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
    @mock.patch('ai.api.permissions.feature_flags')
    def test_featureflag_off_get_model_id(self, feature_flags, *args):
        def get_feature_flags(name, *args):
            return ""

        feature_flags.get = get_feature_flags
        self.user.organization_id = "1"
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('wca_model_id'))
        self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
        self.mock_secret_manager.get_secret.assert_not_called()

    @override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
    @mock.patch('ai.api.permissions.feature_flags')
    def test_featureflag_off_set_model_id(self, feature_flags, *args):
        def get_feature_flags(name, *args):
            return ""

        feature_flags.get = get_feature_flags
        self.user.organization_id = "1"
        self.client.force_authenticate(user=self.user)
        r = self.client.post(
            reverse('wca_model_id'),
            data='{ "model_id": "secret_model_id" }',
            content_type='application/json',
        )
        self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
        self.mock_secret_manager.save_secret.assert_not_called()


@override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
@patch.object(IsWCAModelIdApiFeatureFlagOn, 'has_permission', return_value=True)
@patch.object(IsOrganisationAdministrator, 'has_permission', return_value=True)
@patch.object(IsOrganisationLightspeedSubscriber, 'has_permission', return_value=True)
class TestWCAModelIdView(WisdomServiceAPITestCaseBase):
    def setUp(self):
        super().setUp()
        self.secret_manager_patcher = patch.object(
            apps.get_app_config('ai'), '_wca_secret_manager', spec=WcaSecretManager
        )
        self.mock_secret_manager = self.secret_manager_patcher.start()

    def tearDown(self):
        self.secret_manager_patcher.stop()

    def test_get_model_id_authentication_error(self, *args):
        # self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('wca_model_id'))
        self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)

    def test_get_key_without_org_id(self, *args):
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('wca_model_id'))
        self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)

    def test_permission_classes(self, *args):
        url = reverse('wca_model_id')
        view = resolve(url).func.view_class

        required_permissions = [
            IsWCAModelIdApiFeatureFlagOn,
            IsAuthenticated,
            IsAuthenticatedOrTokenHasScope,
            IsOrganisationAdministrator,
            IsOrganisationLightspeedSubscriber,
            AcceptedTermsPermission,
        ]
        self.assertEqual(len(view.permission_classes), len(required_permissions))
        for permission in required_permissions:
            self.assertTrue(permission in view.permission_classes)

    def test_get_model_id_when_undefined(self, *args):
        self.user.organization_id = "unknown"
        self.client.force_authenticate(user=self.user)
        self.mock_secret_manager.get_secret.return_value = None
        r = self.client.get(reverse('wca_model_id'))
        self.assertEqual(r.status_code, HTTPStatus.NOT_FOUND)
        self.mock_secret_manager.get_secret.assert_called_with('unknown', Suffixes.MODEL_ID)

    def test_get_model_id_when_defined(self, *args):
        self.user.organization_id = "1"
        self.client.force_authenticate(user=self.user)
        self.mock_secret_manager.get_secret.return_value = {
            'SecretString': 'secret_model_id',
            'CreatedDate': timezone.now().isoformat(),
        }
        r = self.client.get(reverse('wca_model_id'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertEqual(r.data['model_id'], 'secret_model_id')
        self.mock_secret_manager.get_secret.assert_called_with('1', Suffixes.MODEL_ID)

    def test_get_model_id_when_defined_throws_exception(self, *args):
        self.user.organization_id = "1"
        self.client.force_authenticate(user=self.user)
        self.mock_secret_manager.get_secret.side_effect = WcaSecretManagerError('Test')
        r = self.client.get(reverse('wca_model_id'))
        self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)

    def test_set_model_id_authentication_error(self, *args):
        # self.client.force_authenticate(user=self.user)
        r = self.client.post(reverse('wca_model_id'))
        self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)

    def test_set_key_without_org_id(self, *args):
        self.client.force_authenticate(user=self.user)
        r = self.client.post(reverse('wca_model_id'))
        self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)

    def test_set_model_id(self, *args):
        self.user.organization_id = "1"
        self.client.force_authenticate(user=self.user)
        self.mock_secret_manager.get_secret.return_value = None
        r = self.client.get(reverse('wca_model_id'))
        self.assertEqual(r.status_code, HTTPStatus.NOT_FOUND)
        self.mock_secret_manager.get_secret.assert_called_with('1', Suffixes.MODEL_ID)

        # Set ModelId
        r = self.client.post(
            reverse('wca_model_id'),
            data='{ "model_id": "secret_model_id" }',
            content_type='application/json',
        )
        self.assertEqual(r.status_code, HTTPStatus.NO_CONTENT)
        self.mock_secret_manager.save_secret.assert_called_with(
            '1', Suffixes.MODEL_ID, 'secret_model_id'
        )

        # Check ModelId was stored
        self.mock_secret_manager.get_secret.return_value = {
            'SecretString': 'secret_model_id',
            'CreatedDate': timezone.now().isoformat(),
        }
        r = self.client.get(reverse('wca_model_id'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertEqual(r.data['model_id'], 'secret_model_id')
        self.mock_secret_manager.get_secret.assert_called_with('1', Suffixes.MODEL_ID)

    def test_set_model_id_throws_secret_manager_exception(self, *args):
        self.user.organization_id = "1"
        self.client.force_authenticate(user=self.user)
        self.mock_secret_manager.save_secret.side_effect = WcaSecretManagerError('Test')
        r = self.client.post(
            reverse('wca_model_id'),
            data='{ "model_id": "secret_model_id" }',
            content_type='application/json',
        )
        self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)

    def test_set_model_id_throws_validation_exception(self, *args):
        self.user.organization_id = "1"
        self.client.force_authenticate(user=self.user)
        self.mock_secret_manager.save_secret.side_effect = WcaSecretManagerError('Test')
        r = self.client.post(
            reverse('wca_model_id'),
            data='{ "unknown_json_field": "secret_model_id" }',
            content_type='application/json',
        )
        self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)


@override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
@patch.object(IsWCAModelIdApiFeatureFlagOn, 'has_permission', return_value=True)
@patch.object(IsOrganisationAdministrator, 'has_permission', return_value=True)
@patch.object(IsOrganisationLightspeedSubscriber, 'has_permission', return_value=False)
class TestWCAModelIdViewAsNonSubscriber(WisdomServiceAPITestCaseBase):
    def test_get_model_id_as_non_subscriber(self, *args):
        self.user.organization_id = "1"
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('wca_model_id'))
        self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)


@override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
@patch.object(IsWCAModelIdApiFeatureFlagOn, 'has_permission', return_value=True)
@patch.object(IsOrganisationAdministrator, 'has_permission', return_value=True)
@patch.object(IsOrganisationLightspeedSubscriber, 'has_permission', return_value=True)
class TestWCAModelIdValidatorView(WisdomServiceAPITestCaseBase):
    def test_validate_model_id_authentication_error(self, *args):
        # self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('wca_model_id_validator'))
        self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)

    def test_validate_model_id_without_org_id(self, *args):
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('wca_model_id_validator'))
        self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)

    @mock.patch('ai.api.permissions.feature_flags')
    def test_validate_model_id(self, feature_flags, *args):
        def get_feature_flags(name, *args):
            return "true"

        feature_flags.get = get_feature_flags
        self.user.organization_id = "1"
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('wca_model_id_validator'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
