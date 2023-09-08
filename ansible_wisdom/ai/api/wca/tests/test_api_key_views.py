from http import HTTPStatus
from unittest import mock
from unittest.mock import Mock, patch

from ai.api.aws.exceptions import WcaSecretManagerError
from ai.api.aws.wca_secret_manager import Suffixes, WcaSecretManager
from ai.api.permissions import (
    IsOrganisationAdministrator,
    IsOrganisationLightspeedSubscriber,
    IsWCAKeyApiFeatureFlagOn,
)
from ai.api.tests.test_views import WisdomServiceAPITestCaseBase
from django.apps import apps
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone


@patch.object(IsOrganisationAdministrator, 'has_permission', return_value=True)
@patch.object(IsOrganisationLightspeedSubscriber, 'has_permission', return_value=True)
class TestWCAKeyFeatureFlagView(WisdomServiceAPITestCaseBase):
    @override_settings(LAUNCHDARKLY_SDK_KEY=None)
    def test_featureflag_disabled(self, *args):
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('wca_api_key'))
        self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
        r = self.client.post(reverse('wca_api_key'))
        self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)

    @override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
    @mock.patch('ai.api.permissions.feature_flags')
    def test_featureflag_on_get_key(self, feature_flags, *args):
        def get_feature_flags(name, *args):
            return "true"

        feature_flags.get = get_feature_flags
        self.user.organization_id = "1"
        self.client.force_authenticate(user=self.user)
        mock_secret_mgr = Mock(WcaSecretManager)
        with patch.object(
            apps.get_app_config('ai'),
            '_wca_secret_manager',
            mock_secret_mgr,
        ):
            mock_secret_mgr.get_secret.return_value = {'CreatedDate': timezone.now().isoformat()}
            r = self.client.get(reverse('wca_api_key'))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            mock_secret_mgr.get_secret.assert_called_once_with('1', Suffixes.API_KEY)

    @override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
    @mock.patch('ai.api.permissions.feature_flags')
    def test_featureflag_on_set_key(self, feature_flags, *args):
        def get_feature_flags(name, *args):
            return "true"

        feature_flags.get = get_feature_flags
        self.user.organization_id = "1"
        self.client.force_authenticate(user=self.user)
        mock_secret_mgr = Mock(WcaSecretManager)
        with patch.object(
            apps.get_app_config('ai'),
            '_wca_secret_manager',
            mock_secret_mgr,
        ):
            r = self.client.post(
                reverse('wca_api_key'),
                data='{ "key": "a-key" }',
                content_type='application/json',
            )
            self.assertEqual(r.status_code, HTTPStatus.NO_CONTENT)
            mock_secret_mgr.save_secret.assert_called_once_with('1', Suffixes.API_KEY, 'a-key')

    @override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
    @mock.patch('ai.api.permissions.feature_flags')
    def test_featureflag_off_get_key(self, feature_flags, *args):
        def get_feature_flags(name, *args):
            return ""

        feature_flags.get = get_feature_flags
        self.user.organization_id = "1"
        self.client.force_authenticate(user=self.user)
        mock_secret_mgr = Mock(WcaSecretManager)
        with patch.object(
            apps.get_app_config('ai'),
            '_wca_secret_manager',
            mock_secret_mgr,
        ):
            r = self.client.get(reverse('wca_api_key'))
            self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
            mock_secret_mgr.get_secret.assert_not_called()

    @override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
    @mock.patch('ai.api.permissions.feature_flags')
    def test_featureflag_off_set(self, feature_flags, *args):
        def get_feature_flags(name, *args):
            return ""

        feature_flags.get = get_feature_flags
        self.user.organization_id = "1"
        self.client.force_authenticate(user=self.user)
        mock_secret_mgr = Mock(WcaSecretManager)
        with patch.object(
            apps.get_app_config('ai'),
            '_wca_secret_manager',
            mock_secret_mgr,
        ):
            r = self.client.post(
                reverse('wca_api_key'),
                data='{ "key": "a-key" }',
                content_type='application/json',
            )
            self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
            mock_secret_mgr.save_secret.assert_not_called()


@override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
@patch.object(IsWCAKeyApiFeatureFlagOn, 'has_permission', return_value=True)
@patch.object(IsOrganisationAdministrator, 'has_permission', return_value=True)
@patch.object(IsOrganisationLightspeedSubscriber, 'has_permission', return_value=True)
class TestWCAApiKeyView(WisdomServiceAPITestCaseBase):
    def test_authentication_error(self, *args):
        # self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('wca_api_key'))
        self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)

    def test_get_key_when_undefined(self, *args):
        self.user.organization_id = "unknown"
        self.client.force_authenticate(user=self.user)
        mock_secret_manager = Mock(WcaSecretManager)

        with patch.object(
            apps.get_app_config('ai'),
            '_wca_secret_manager',
            mock_secret_manager,
        ):
            mock_secret_manager.get_secret.return_value = None
            r = self.client.get(reverse('wca_api_key'))
            self.assertEqual(r.status_code, HTTPStatus.NOT_FOUND)
            mock_secret_manager.get_secret.assert_called_with('unknown', Suffixes.API_KEY)

    def test_get_key_when_defined(self, *args):
        self.user.organization_id = "1"
        self.client.force_authenticate(user=self.user)
        mock_secret_manager = Mock(WcaSecretManager)

        with patch.object(
            apps.get_app_config('ai'),
            '_wca_secret_manager',
            mock_secret_manager,
        ):
            mock_secret_manager.get_secret.return_value = {
                'CreatedDate': timezone.now().isoformat()
            }
            r = self.client.get(reverse('wca_api_key'))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            mock_secret_manager.get_secret.assert_called_with('1', Suffixes.API_KEY)

    def test_get_key_when_defined_throws_exception(self, *args):
        self.user.organization_id = "1"
        self.client.force_authenticate(user=self.user)
        mock_secret_manager = Mock(WcaSecretManager)

        with patch.object(
            apps.get_app_config('ai'),
            '_wca_secret_manager',
            mock_secret_manager,
        ):
            mock_secret_manager.get_secret.side_effect = WcaSecretManagerError('Test')
            r = self.client.get(reverse('wca_api_key'))
            self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)

    def test_set_key(self, *args):
        self.user.organization_id = "1"
        self.client.force_authenticate(user=self.user)
        mock_secret_manager = Mock(WcaSecretManager)

        # Key should initially not exist
        with patch.object(
            apps.get_app_config('ai'),
            '_wca_secret_manager',
            mock_secret_manager,
        ):
            mock_secret_manager.get_secret.return_value = None
            r = self.client.get(reverse('wca_api_key'))
            self.assertEqual(r.status_code, HTTPStatus.NOT_FOUND)
            mock_secret_manager.get_secret.assert_called_with('1', Suffixes.API_KEY)

            # Set Key
            r = self.client.post(
                reverse('wca_api_key'),
                data='{ "key": "a-new-key" }',
                content_type='application/json',
            )
            self.assertEqual(r.status_code, HTTPStatus.NO_CONTENT)
            mock_secret_manager.save_secret.assert_called_with('1', Suffixes.API_KEY, 'a-new-key')

            # Check Key was stored
            mock_secret_manager.get_secret.return_value = {
                'CreatedDate': timezone.now().isoformat()
            }
            r = self.client.get(reverse('wca_api_key'))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            mock_secret_manager.get_secret.assert_called_with('1', Suffixes.API_KEY)

    def test_set_key_throws_secret_manager_exception(self, *args):
        self.user.organization_id = "1"
        self.client.force_authenticate(user=self.user)
        mock_secret_manager = Mock(WcaSecretManager)

        with patch.object(
            apps.get_app_config('ai'),
            '_wca_secret_manager',
            mock_secret_manager,
        ):
            mock_secret_manager.save_secret.side_effect = WcaSecretManagerError('Test')
            r = self.client.post(
                reverse('wca_api_key'),
                data='{ "key": "a-new-key" }',
                content_type='application/json',
            )
            self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)

    def test_set_key_throws_validation_exception(self, *args):
        self.user.organization_id = "1"
        self.client.force_authenticate(user=self.user)
        mock_secret_manager = Mock(WcaSecretManager)

        with patch.object(
            apps.get_app_config('ai'),
            '_wca_secret_manager',
            mock_secret_manager,
        ):
            r = self.client.post(
                reverse('wca_api_key'),
                data='{ "unknown_json_field": "a-new-key" }',
                content_type='application/json',
            )
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)


@override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
@patch.object(IsWCAKeyApiFeatureFlagOn, 'has_permission', return_value=True)
@patch.object(IsOrganisationAdministrator, 'has_permission', return_value=True)
@patch.object(IsOrganisationLightspeedSubscriber, 'has_permission', return_value=False)
class TestWCAApiKeyViewAsNonSubscriber(WisdomServiceAPITestCaseBase):
    def test_get_api_key_as_non_subscriber(self, *args):
        self.user.organization_id = "1"
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('wca_api_key'))
        self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)


@override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
@patch.object(IsWCAKeyApiFeatureFlagOn, 'has_permission', return_value=True)
@patch.object(IsOrganisationAdministrator, 'has_permission', return_value=True)
@patch.object(IsOrganisationLightspeedSubscriber, 'has_permission', return_value=True)
class TestWCAApiKeyValidatorView(WisdomServiceAPITestCaseBase):
    def test_authentication_error(self, *args):
        # self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('wca_api_key_validator'))
        self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)

    @mock.patch('ai.api.permissions.feature_flags')
    def test_validate_key(self, feature_flags, *args):
        def get_feature_flags(name, *args):
            return "true"

        feature_flags.get = get_feature_flags
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('wca_api_key_validator'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
