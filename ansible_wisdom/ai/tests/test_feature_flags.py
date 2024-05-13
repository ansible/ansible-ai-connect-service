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

import tempfile
from unittest.mock import patch

from django.conf import settings
from django.test import override_settings
from ldclient.config import Config

import ansible_ai_connect.ai.feature_flags as feature_flags
from ansible_ai_connect.ai.api.tests.test_views import WisdomServiceAPITestCaseBase


class TestFeatureFlags(WisdomServiceAPITestCaseBase):
    def setUp(self):
        super().setUp()
        feature_flags.FeatureFlags.instance = None

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

    def test_feature_flags_with_local_file(self):
        fd = tempfile.NamedTemporaryFile()
        fd.write(
            b"""
        {
          "flagValues": {
            "model_name": "dev_model",
            "my-boolean-flag-key": true,
            "my-integer-flag-key": 3
          }
        }
        """
        )
        fd.seek(0)
        with self.settings(LAUNCHDARKLY_SDK_KEY=fd.name):
            ff = feature_flags.FeatureFlags()
            value = ff.get('model_name', self.user, 'default_value')
            self.assertEqual(ff.client.get_sdk_key(), 'sdk-key-123abc')
            self.assertEqual(value, 'dev_model')
        fd.close()
