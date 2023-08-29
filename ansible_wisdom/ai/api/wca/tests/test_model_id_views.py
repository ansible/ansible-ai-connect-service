from http import HTTPStatus
from unittest import mock
from unittest.mock import Mock, patch

from ai.api.aws.exceptions import WcaSecretManagerError
from ai.api.aws.wca_secret_manager import Suffixes, WcaSecretManager
from ai.api.permissions import IsWCAModelIdApiFeatureFlagOn
from ai.api.tests.test_views import WisdomServiceAPITestCaseBase
from django.apps import apps
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone


class TestWCAModelIdFeatureFlagView(WisdomServiceAPITestCaseBase):
    @override_settings(LAUNCHDARKLY_SDK_KEY=None)
    def test_featureflag_disabled(self):
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('wca_model_id', kwargs={'org_id': '1'}))
        self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
        r = self.client.post(reverse('wca_model_id', kwargs={'org_id': '1'}))
        self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)

    @override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
    @mock.patch('ai.api.permissions.feature_flags')
    def test_featureflag_on_get_model_id(self, feature_flags):
        def get_feature_flags(name, *args):
            return "true"

        feature_flags.get = get_feature_flags
        self.client.force_authenticate(user=self.user)
        mock_secret_mgr = Mock(WcaSecretManager)
        with patch.object(
            apps.get_app_config('ai'),
            '_wca_secret_manager',
            mock_secret_mgr,
        ):
            mock_secret_mgr.get_secret.return_value = {'SecretString': '1', 'CreatedDate': '0'}
            r = self.client.get(reverse('wca_model_id', kwargs={'org_id': '1'}))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            mock_secret_mgr.get_secret.assert_called_once_with('1', Suffixes.MODEL_ID)

    @override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
    @mock.patch('ai.api.permissions.feature_flags')
    def test_featureflag_on_set_model_id(self, feature_flags):
        def get_feature_flags(name, *args):
            return "true"

        feature_flags.get = get_feature_flags
        self.client.force_authenticate(user=self.user)
        mock_secret_mgr = Mock(WcaSecretManager)
        with patch.object(
            apps.get_app_config('ai'),
            '_wca_secret_manager',
            mock_secret_mgr,
        ):
            r = self.client.post(
                reverse('wca_model_id', kwargs={'org_id': '1'}),
                data='{ "model_id": "secret_model_id" }',
                content_type='application/json',
            )
            self.assertEqual(r.status_code, HTTPStatus.NO_CONTENT)
            mock_secret_mgr.save_secret.assert_called_once_with(
                '1', Suffixes.MODEL_ID, 'secret_model_id'
            )

    @override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
    @mock.patch('ai.api.permissions.feature_flags')
    def test_featureflag_off_get_model_id(self, feature_flags):
        def get_feature_flags(name, *args):
            return ""

        feature_flags.get = get_feature_flags
        self.client.force_authenticate(user=self.user)
        mock_secret_mgr = Mock(WcaSecretManager)
        with patch.object(
            apps.get_app_config('ai'),
            '_wca_secret_manager',
            mock_secret_mgr,
        ):
            r = self.client.get(reverse('wca_model_id', kwargs={'org_id': '1'}))
            self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
            mock_secret_mgr.get_secret.assert_not_called()

    @override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
    @mock.patch('ai.api.permissions.feature_flags')
    def test_featureflag_off_set_model_id(self, feature_flags):
        def get_feature_flags(name, *args):
            return ""

        feature_flags.get = get_feature_flags
        self.client.force_authenticate(user=self.user)
        mock_secret_mgr = Mock(WcaSecretManager)
        with patch.object(
            apps.get_app_config('ai'),
            '_wca_secret_manager',
            mock_secret_mgr,
        ):
            r = self.client.post(
                reverse('wca_model_id', kwargs={'org_id': '1'}),
                data='{ "model_id": "secret_model_id" }',
                content_type='application/json',
            )
            self.assertEqual(r.status_code, HTTPStatus.FORBIDDEN)
            mock_secret_mgr.save_secret.assert_not_called()


@override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
@patch.object(IsWCAModelIdApiFeatureFlagOn, 'has_permission', return_value=True)
class TestWCAModelIdView(WisdomServiceAPITestCaseBase):
    def test_authentication_error(self, _):
        # self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse('wca_model_id', kwargs={'org_id': '1'}))
        self.assertEqual(r.status_code, HTTPStatus.UNAUTHORIZED)

    def test_get_model_id_when_undefined(self, _):
        self.client.force_authenticate(user=self.user)
        mock_secret_manager = Mock(WcaSecretManager)

        with patch.object(
            apps.get_app_config('ai'),
            '_wca_secret_manager',
            mock_secret_manager,
        ):
            mock_secret_manager.get_secret.return_value = None
            r = self.client.get(reverse('wca_model_id', kwargs={'org_id': 'unknown'}))
            self.assertEqual(r.status_code, HTTPStatus.NOT_FOUND)
            mock_secret_manager.get_secret.assert_called_with('unknown', Suffixes.MODEL_ID)

    def test_get_model_id_when_defined(self, _):
        self.client.force_authenticate(user=self.user)
        mock_secret_manager = Mock(WcaSecretManager)

        with patch.object(
            apps.get_app_config('ai'),
            '_wca_secret_manager',
            mock_secret_manager,
        ):
            mock_secret_manager.get_secret.return_value = {
                'SecretString': 'secret_model_id',
                'CreatedDate': timezone.now().isoformat(),
            }
            r = self.client.get(reverse('wca_model_id', kwargs={'org_id': '1'}))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            self.assertEqual(r.data['model_id'], 'secret_model_id')
            mock_secret_manager.get_secret.assert_called_with('1', Suffixes.MODEL_ID)

    def test_get_model_id_when_defined_throws_exception(self, _):
        self.client.force_authenticate(user=self.user)
        mock_secret_manager = Mock(WcaSecretManager)

        with patch.object(
            apps.get_app_config('ai'),
            '_wca_secret_manager',
            mock_secret_manager,
        ):
            mock_secret_manager.get_secret.side_effect = WcaSecretManagerError('Test')
            r = self.client.get(reverse('wca_model_id', kwargs={'org_id': '1'}))
            self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)

    def test_set_model_id(self, _):
        self.client.force_authenticate(user=self.user)
        mock_secret_manager = Mock(WcaSecretManager)

        # ModelId should initially not exist
        with patch.object(
            apps.get_app_config('ai'),
            '_wca_secret_manager',
            mock_secret_manager,
        ):
            mock_secret_manager.get_secret.return_value = None
            r = self.client.get(reverse('wca_model_id', kwargs={'org_id': '1'}))
            self.assertEqual(r.status_code, HTTPStatus.NOT_FOUND)
            mock_secret_manager.get_secret.assert_called_with('1', Suffixes.MODEL_ID)

            # Set ModelId
            r = self.client.post(
                reverse('wca_model_id', kwargs={'org_id': '1'}),
                data='{ "model_id": "secret_model_id" }',
                content_type='application/json',
            )
            self.assertEqual(r.status_code, HTTPStatus.NO_CONTENT)
            mock_secret_manager.save_secret.assert_called_with(
                '1', Suffixes.MODEL_ID, 'secret_model_id'
            )

            # Check ModelId was stored
            mock_secret_manager.get_secret.return_value = {
                'SecretString': 'secret_model_id',
                'CreatedDate': timezone.now().isoformat(),
            }
            r = self.client.get(reverse('wca_model_id', kwargs={'org_id': '1'}))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            self.assertEqual(r.data['model_id'], 'secret_model_id')
            mock_secret_manager.get_secret.assert_called_with('1', Suffixes.MODEL_ID)

    def test_set_model_id_throws_secret_manager_exception(self, _):
        self.client.force_authenticate(user=self.user)
        mock_secret_manager = Mock(WcaSecretManager)

        with patch.object(
            apps.get_app_config('ai'),
            '_wca_secret_manager',
            mock_secret_manager,
        ):
            mock_secret_manager.save_secret.side_effect = WcaSecretManagerError('Test')
            r = self.client.post(
                reverse('wca_model_id', kwargs={'org_id': '1'}),
                data='{ "model_id": "secret_model_id" }',
                content_type='application/json',
            )
            self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)

    def test_set_model_id_throws_validation_exception(self, _):
        self.client.force_authenticate(user=self.user)
        mock_secret_manager = Mock(WcaSecretManager)

        with patch.object(
            apps.get_app_config('ai'),
            '_wca_secret_manager',
            mock_secret_manager,
        ):
            mock_secret_manager.save_secret.side_effect = WcaSecretManagerError('Test')
            r = self.client.post(
                reverse('wca_model_id', kwargs={'org_id': '1'}),
                data='{ "unknown_json_field": "secret_model_id" }',
                content_type='application/json',
            )
            self.assertEqual(r.status_code, HTTPStatus.BAD_REQUEST)
