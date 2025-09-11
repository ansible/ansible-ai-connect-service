#!/usr/bin/env python3

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

"""
Unit tests for WCA pipeline SSL configuration with infrastructure-first SSL manager.

This test suite validates the SSL manager integration for WCA pipelines
to ensure external service connectivity works correctly with centralized SSL management.
"""

from unittest.mock import Mock, patch

import requests
from django.test import SimpleTestCase

from ansible_ai_connect.ai.api.model_pipelines.wca.configuration_onprem import (
    WCAOnPremConfiguration,
)
from ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_onprem import (
    WCAOnPremMetaData,
)


class TestWCABaseMetaDataSSL(SimpleTestCase):
    """Test SSL manager integration for WCABaseMetaData class."""

    def _create_mock_config(self, verify_ssl=True, api_key="test-key"):
        """Create a mock WCA configuration for testing."""
        config = Mock(spec=WCAOnPremConfiguration)
        config.verify_ssl = verify_ssl
        config.api_key = api_key
        config.url = "https://test-wca.example.com"
        config.retry_count = 3
        config.timeout = 30
        config.username = "test_user"
        config.health_check_api_key = "test_health_key"
        config.health_check_model_id = "test_model"
        return config

    @patch("ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_base.ssl_manager")
    def test_ssl_manager_integration_verify_ssl_enabled(self, mock_ssl_manager):
        """Test that WCAOnPremMetaData uses SSL manager when verify_ssl is enabled."""
        config = self._create_mock_config(verify_ssl=True)
        mock_session = Mock(spec=requests.Session)
        mock_ssl_manager.get_requests_session.return_value = mock_session

        # Create metadata instance
        metadata = WCAOnPremMetaData(config)

        # Verify SSL manager was called with correct parameters
        mock_ssl_manager.get_requests_session.assert_called_once_with(verify_ssl=True)

        # Verify the session was assigned correctly
        self.assertEqual(metadata.session, mock_session)
        self.assertIsNotNone(metadata)

    @patch("ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_base.ssl_manager")
    def test_ssl_manager_integration_verify_ssl_disabled(self, mock_ssl_manager):
        """Test that WCAOnPremMetaData uses SSL manager when verify_ssl is disabled."""
        config = self._create_mock_config(verify_ssl=False)
        mock_session = Mock(spec=requests.Session)
        mock_ssl_manager.get_requests_session.return_value = mock_session

        # Create metadata instance
        metadata = WCAOnPremMetaData(config)

        # Verify SSL manager was called with correct parameters
        mock_ssl_manager.get_requests_session.assert_called_once_with(verify_ssl=False)

        # Verify the session was assigned correctly
        self.assertEqual(metadata.session, mock_session)
        self.assertIsNotNone(metadata)

    @patch("ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_base.ssl_manager")
    def test_ssl_manager_session_fallback_on_error(self, mock_ssl_manager):
        """Test that WCAOnPremMetaData falls back to basic session on SSL manager error."""
        config = self._create_mock_config(verify_ssl=True)

        # Mock SSL manager to raise an exception
        mock_ssl_manager.get_requests_session.side_effect = requests.exceptions.RequestException(
            "SSL configuration failed"
        )

        with patch(
            "ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_base.requests.Session"
        ) as mock_session_class:
            mock_basic_session = Mock()
            mock_session_class.return_value = mock_basic_session
            # Create metadata instance
            metadata = WCAOnPremMetaData(config)
            # Verify SSL manager was called
            mock_ssl_manager.get_requests_session.assert_called_once_with(verify_ssl=True)
            # Verify fallback session was created and used
            mock_session_class.assert_called_once()
            self.assertEqual(metadata.session, mock_basic_session)
            self.assertIsNotNone(metadata)

    @patch("ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_base.ssl_manager")
    def test_ssl_manager_preserves_config_attributes(self, mock_ssl_manager):
        """Test that SSL manager integration preserves all config attributes."""
        config = self._create_mock_config(verify_ssl=True)
        config.retry_count = 5
        config.timeout = 45

        mock_session = Mock(spec=requests.Session)
        mock_ssl_manager.get_requests_session.return_value = mock_session

        # Create metadata instance
        metadata = WCAOnPremMetaData(config)

        # Verify all config attributes are preserved
        self.assertEqual(metadata.config, config)
        self.assertEqual(metadata.retries, 5)
        self.assertEqual(metadata._timeout, 45)
        self.assertEqual(metadata.session, mock_session)

    @patch("ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_base.ssl_manager")
    def test_task_gen_timeout_calculation(self, mock_ssl_manager):
        """Test task generation timeout calculation works correctly."""
        config = self._create_mock_config()
        config.timeout = 30

        mock_session = Mock(spec=requests.Session)
        mock_ssl_manager.get_requests_session.return_value = mock_session

        metadata = WCAOnPremMetaData(config)

        # Test timeout calculation
        self.assertEqual(metadata.task_gen_timeout(1), 30)
        self.assertEqual(metadata.task_gen_timeout(2), 60)
        self.assertEqual(metadata.task_gen_timeout(3), 90)

    @patch("ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_base.ssl_manager")
    def test_task_gen_timeout_with_none_timeout(self, mock_ssl_manager):
        """Test task generation timeout when config timeout is None."""
        config = self._create_mock_config()
        config.timeout = None

        mock_session = Mock(spec=requests.Session)
        mock_ssl_manager.get_requests_session.return_value = mock_session

        metadata = WCAOnPremMetaData(config)

        # Test timeout calculation with None
        self.assertIsNone(metadata.task_gen_timeout(1))
        self.assertIsNone(metadata.task_gen_timeout(5))


class TestWCASSLConfigurationIntegration(SimpleTestCase):
    """Test integration of WCA with SSL manager across different scenarios."""

    def _create_mock_config(self, verify_ssl=True):
        """Create a mock WCA configuration."""
        config = Mock(spec=WCAOnPremConfiguration)
        config.verify_ssl = verify_ssl
        config.retry_count = 3
        config.timeout = 30
        config.username = "test_user"
        config.api_key = "test_api_key"
        config.health_check_api_key = "test_health_key"
        config.health_check_model_id = "test_model"
        return config

    @patch("ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_base.ssl_manager")
    def test_ssl_verification_configuration(self, mock_ssl_manager):
        """Test SSL verification configuration for different settings."""
        mock_session = Mock(spec=requests.Session)
        mock_ssl_manager.get_requests_session.return_value = mock_session

        # Test with SSL verification enabled
        config_ssl_enabled = self._create_mock_config(verify_ssl=True)
        metadata_ssl_enabled = WCAOnPremMetaData(config_ssl_enabled)

        # Test with SSL verification disabled
        config_ssl_disabled = self._create_mock_config(verify_ssl=False)
        metadata_ssl_disabled = WCAOnPremMetaData(config_ssl_disabled)

        # Verify SSL manager was called with correct parameters for both cases
        calls = mock_ssl_manager.get_requests_session.call_args_list
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0].kwargs["verify_ssl"], True)
        self.assertEqual(calls[1].kwargs["verify_ssl"], False)

        # Verify both instances were created successfully
        self.assertIsNotNone(metadata_ssl_enabled)
        self.assertIsNotNone(metadata_ssl_disabled)

    @patch("ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_base.ssl_manager")
    def test_task_gen_timeout_functionality(self, mock_ssl_manager):
        """Test task generation timeout calculation."""
        config = self._create_mock_config()
        config.timeout = 25
        mock_session = Mock(spec=requests.Session)
        mock_ssl_manager.get_requests_session.return_value = mock_session

        metadata = WCAOnPremMetaData(config)

        # Test various task counts
        self.assertEqual(metadata.task_gen_timeout(1), 25)
        self.assertEqual(metadata.task_gen_timeout(2), 50)
        self.assertEqual(metadata.task_gen_timeout(4), 100)

    @patch("ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_base.ssl_manager")
    def test_timeout_none_handling(self, mock_ssl_manager):
        """Test handling when timeout is None."""
        config = self._create_mock_config()
        config.timeout = None

        mock_session = Mock(spec=requests.Session)
        mock_ssl_manager.get_requests_session.return_value = mock_session

        metadata = WCAOnPremMetaData(config)

        # When timeout is None, task_gen_timeout should return None regardless of task count
        self.assertIsNone(metadata.task_gen_timeout(1))
        self.assertIsNone(metadata.task_gen_timeout(10))

    @patch("ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_base.ssl_manager")
    def test_wca_ssl_with_real_session(self, mock_ssl_manager):
        """Test WCA SSL configuration with real session object."""
        config = self._create_mock_config(verify_ssl=True)

        # Use a real session object to test integration
        real_session = requests.Session()
        mock_ssl_manager.get_requests_session.return_value = real_session

        metadata = WCAOnPremMetaData(config)

        # Verify the real session is used
        self.assertEqual(metadata.session, real_session)
        self.assertIsInstance(metadata.session, requests.Session)

        # Verify SSL manager was called correctly
        mock_ssl_manager.get_requests_session.assert_called_once_with(verify_ssl=True)
