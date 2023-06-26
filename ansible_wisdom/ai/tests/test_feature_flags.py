from unittest.mock import patch

from ai.api.tests.test_views import WisdomServiceAPITestCaseBase
from django.test import override_settings

from ..feature_flags import FeatureFlags


class TestFeatureFlags(WisdomServiceAPITestCaseBase):
    @override_settings(LAUNCHDARKLY_SDK_KEY=None)
    def test_feature_flags_without_sdk_key(self):
        ff = FeatureFlags()
        with self.assertRaises(Exception) as ex:
            ff.get('model_name', None, 'default_value')
            self.assertEqual(str(ex), 'feature flag client is not initialized')

    @override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
    @patch('ldclient.get')
    def test_feature_flags_with_sdk_key(self, ldclient_get):
        class DummyClient:
            def variation(name, *args):
                return 'server:port:model_name:index'

        ldclient_get.return_value = DummyClient()
        ff = FeatureFlags()
        value = ff.get('model_name', self.user, 'default_value')
        self.assertEqual(value, 'server:port:model_name:index')
