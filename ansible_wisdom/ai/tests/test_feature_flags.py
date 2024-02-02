from os import path
from unittest.mock import patch

import ai.feature_flags as feature_flags
from ai.api.tests.test_views import WisdomServiceAPITestCaseBase
from django.conf import settings
from django.test import override_settings
from ldclient.config import Config


class TestFeatureFlags(WisdomServiceAPITestCaseBase):
    @override_settings(LAUNCHDARKLY_SDK_KEY=None)
    def test_feature_flags_without_sdk_key(self):
        ff = feature_flags.FeatureFlags()
        with self.assertRaises(Exception) as ex:
            ff.get('model_name', None, 'default_value')
            self.assertEqual(str(ex), 'feature flag client is not initialized')

    @override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
    @patch.object(feature_flags, 'LDClient')
    def test_feature_flags_with_sdk_key(self, LDClient):
        LDClient.return_value.variation.return_value = 'server:port:model_name:index'

        ff = feature_flags.FeatureFlags()
        value = ff.get('model_name', self.user, 'default_value')
        self.assert_test_feature_flags_with_sdk_key(LDClient, value)

    @override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
    @patch.object(feature_flags, 'LDClient')
    def test_feature_flags_with_sdk_key_without_user(self, LDClient):
        LDClient.return_value.variation.return_value = 'server:port:model_name:index'

        ff = feature_flags.FeatureFlags()
        value = ff.get('model_name', None, 'default_value')
        self.assert_test_feature_flags_with_sdk_key(LDClient, value)

    def assert_test_feature_flags_with_sdk_key(self, LDClient, value):
        self.assertEqual(value, 'server:port:model_name:index')
        LDClient.assert_called_once()
        _, config_arg, kwargs = LDClient.mock_calls[0]
        self.assertIsInstance(config_arg[0], Config)
        self.assertEqual(config_arg[0].sdk_key, 'dummy_key')
        self.assertEqual(kwargs['start_wait'], settings.LAUNCHDARKLY_SDK_TIMEOUT)

    @override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
    @override_settings(LAUNCHDARKLY_SDK_TIMEOUT=40)
    @patch.object(feature_flags, 'LDClient')
    def test_feature_flags_with_sdk_timeout(self, LDClient):
        LDClient.return_value.variation.return_value = 'server:port:model_name:index'

        feature_flags.FeatureFlags()

        LDClient.assert_called_once()
        _, config_arg, kwargs = LDClient.mock_calls[0]
        self.assertIsInstance(config_arg[0], Config)
        self.assertEqual(config_arg[0].sdk_key, 'dummy_key')
        self.assertEqual(kwargs['start_wait'], 40)

    @override_settings(LAUNCHDARKLY_SDK_KEY=path.join(settings.BASE_DIR, '../../flagdata.json'))
    def test_feature_flags_with_local_file(self):
        ff = feature_flags.FeatureFlags()
        value = ff.get('model_name', self.user, 'default_value')
        self.assertEqual(ff.client.get_sdk_key(), 'sdk-key-123abc')
        self.assertEqual(value, 'dev_model')
