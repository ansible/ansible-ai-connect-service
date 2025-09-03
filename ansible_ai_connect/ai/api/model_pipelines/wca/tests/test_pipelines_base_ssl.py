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
Unit tests for WCA pipeline SSL configuration in pipelines_base.py.

This test suite validates the SSL context setup and configuration
for WCA pipelines to ensure external service connectivity works correctly.
"""

import os
import ssl
import tempfile
from unittest.mock import Mock, patch

import requests.adapters
from django.test import SimpleTestCase, override_settings

from ansible_ai_connect.ai.api.model_pipelines.wca.configuration_onprem import (
    WCAOnPremConfiguration,
)
from ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_onprem import (
    WCAOnPremMetaData,
)


class TestWCABaseMetaDataSSL(SimpleTestCase):
    """Test SSL configuration for WCABaseMetaData class."""

    def setUp(self):
        """Set up test environment."""
        # Store original environment variables
        self.original_ca_bundle = os.environ.get("REQUESTS_CA_BUNDLE")
        self.original_ssl_cert = os.environ.get("SSL_CERT_FILE")

    def tearDown(self):
        """Clean up test environment."""
        # Restore original environment variables
        if self.original_ca_bundle:
            os.environ["REQUESTS_CA_BUNDLE"] = self.original_ca_bundle
        else:
            os.environ.pop("REQUESTS_CA_BUNDLE", None)

        if self.original_ssl_cert:
            os.environ["SSL_CERT_FILE"] = self.original_ssl_cert
        else:
            os.environ.pop("SSL_CERT_FILE", None)

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

    def test_setup_ssl_context_with_verify_ssl_enabled(self):
        """Test SSL context setup when verify_ssl is enabled."""
        config = self._create_mock_config(verify_ssl=True)

        with (
            patch("ssl.create_default_context") as mock_ssl_context,
            patch("requests.adapters.HTTPAdapter") as mock_adapter,
        ):

            mock_context = Mock()
            mock_ssl_context.return_value = mock_context
            mock_adapter_instance = Mock()
            mock_adapter.return_value = mock_adapter_instance

            # Create metadata instance
            metadata = WCAOnPremMetaData(config)

            # Verify SSL context was created
            mock_ssl_context.assert_called_once()
            # Verify metadata instance was created successfully
            self.assertIsNotNone(metadata)

            # Verify HTTPAdapter was created and configured
            mock_adapter.assert_called_once()
            mock_adapter_instance.init_poolmanager.assert_called_once_with(
                connections=10, maxsize=10, ssl_context=mock_context
            )

    def test_setup_ssl_context_with_verify_ssl_disabled(self):
        """Test SSL context setup is skipped when verify_ssl is disabled."""
        config = self._create_mock_config(verify_ssl=False)

        with (
            patch("ssl.create_default_context") as mock_ssl_context,
            patch("requests.adapters.HTTPAdapter") as mock_adapter,
        ):

            # Create metadata instance
            metadata = WCAOnPremMetaData(config)

            # Verify SSL context was NOT created when verify_ssl is False
            mock_ssl_context.assert_not_called()
            mock_adapter.assert_not_called()
            # Verify metadata instance was created successfully
            self.assertIsNotNone(metadata)

    @override_settings(SERVICE_CA_PATH="/test/service-ca.crt")
    def test_setup_ssl_context_with_service_ca_detection(self):
        """Test SSL context setup with service CA detection."""
        config = self._create_mock_config(verify_ssl=True)

        with (
            patch("os.path.exists", return_value=True),
            patch("ssl.create_default_context") as mock_ssl_context,
            patch("requests.adapters.HTTPAdapter") as mock_adapter,
            self.assertLogs(
                "ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_base", level="INFO"
            ) as log,
        ):

            mock_context = Mock()
            mock_ssl_context.return_value = mock_context
            mock_adapter_instance = Mock()
            mock_adapter.return_value = mock_adapter_instance

            # Create metadata instance
            metadata = WCAOnPremMetaData(config)

            # Verify SSL context was created
            mock_ssl_context.assert_called_once()
            # Verify metadata instance was created successfully
            self.assertIsNotNone(metadata)

            # Verify service CA detection was logged
            self.assertIn(
                "Service CA detected, using explicit system CAs for external endpoints",
                str(log.output),
            )

    @override_settings(SERVICE_CA_PATH="/nonexistent/service-ca.crt")
    def test_setup_ssl_context_with_nonexistent_custom_service_ca(self):
        """Test SSL context setup when custom service CA file
        doesn't exist - should continue gracefully."""
        config = self._create_mock_config(verify_ssl=True)

        with (
            patch("os.path.exists", return_value=False),
            patch("ssl.create_default_context") as mock_ssl_context,
            patch("requests.adapters.HTTPAdapter") as mock_adapter,
            self.assertLogs(
                "ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_base", level="INFO"
            ) as log,
        ):

            mock_context = Mock()
            mock_ssl_context.return_value = mock_context
            mock_adapter_instance = Mock()
            mock_adapter.return_value = mock_adapter_instance

            # Create metadata instance - should work fine even with missing custom path
            metadata = WCAOnPremMetaData(config)

            # Verify SSL context was created and metadata instance is successful
            mock_ssl_context.assert_called_once()
            self.assertIsNotNone(metadata)

            # Verify appropriate log message for missing certificate
            self.assertIn(
                "WCA SSL: Using explicit system CAs for external endpoints", str(log.output)
            )

    @override_settings(
        SERVICE_CA_PATH="/var/run/secrets/kubernetes.io/serviceaccount/service-ca.crt"
    )
    def test_setup_ssl_context_with_nonexistent_default_service_ca(self):
        """Test SSL context setup when default service CA file
        doesn't exist - should continue gracefully."""
        config = self._create_mock_config(verify_ssl=True)

        with (
            patch("os.path.exists", return_value=False),
            patch("ssl.create_default_context") as mock_ssl_context,
            patch("requests.adapters.HTTPAdapter") as mock_adapter,
            self.assertLogs(
                "ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_base", level="INFO"
            ) as log,
        ):

            mock_context = Mock()
            mock_ssl_context.return_value = mock_context
            mock_adapter_instance = Mock()
            mock_adapter.return_value = mock_adapter_instance

            # Create metadata instance - should work fine with default path missing
            metadata = WCAOnPremMetaData(config)

            # Verify SSL context was created even when default service CA doesn't exist
            mock_ssl_context.assert_called_once()
            # Verify metadata instance was created successfully
            self.assertIsNotNone(metadata)

            # Verify appropriate log message for missing certificate
            self.assertIn(
                "WCA SSL: Using explicit system CAs for external endpoints", str(log.output)
            )

    def test_setup_ssl_context_session_mount(self):
        """Test that SSL adapter is properly mounted to session."""
        config = self._create_mock_config(verify_ssl=True)

        with (
            patch("ssl.create_default_context") as mock_ssl_context,
            patch("requests.adapters.HTTPAdapter") as mock_adapter,
        ):

            mock_context = Mock()
            mock_ssl_context.return_value = mock_context
            mock_adapter_instance = Mock()
            mock_adapter.return_value = mock_adapter_instance

            # Create metadata instance
            metadata = WCAOnPremMetaData(config)

            # Verify SSL context was created
            mock_ssl_context.assert_called_once()
            # Verify metadata instance was created successfully
            self.assertIsNotNone(metadata)

            # Verify HTTPAdapter was created and configured
            mock_adapter.assert_called_once()
            mock_adapter_instance.init_poolmanager.assert_called_once_with(
                connections=10, maxsize=10, ssl_context=mock_context
            )

    def test_ssl_context_resilience_against_environment_pollution(self):
        """Test that WCA SSL context is resilient against environment variable pollution."""
        # Create temporary invalid certificate file
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".crt") as temp_ca:
            temp_ca.write("-----BEGIN CERTIFICATE-----\ninvalid\n-----END CERTIFICATE-----")
            temp_ca_path = temp_ca.name

        try:
            # Pollute environment with invalid SSL settings
            os.environ["REQUESTS_CA_BUNDLE"] = temp_ca_path
            os.environ["SSL_CERT_FILE"] = temp_ca_path

            config = self._create_mock_config(verify_ssl=True)

            with patch("ssl.create_default_context") as mock_ssl_context:
                mock_context = Mock()
                mock_ssl_context.return_value = mock_context

                # Should succeed despite environment pollution
                metadata = WCAOnPremMetaData(config)

                # Verify SSL context was created using proper system defaults
                mock_ssl_context.assert_called_once()
                self.assertIsInstance(metadata.session, requests.Session)

        finally:
            # Clean up temporary file
            os.unlink(temp_ca_path)

    def test_session_https_adapter_configuration(self):
        """Test that session has proper HTTPS adapter configuration."""
        config = self._create_mock_config(verify_ssl=True)

        # Create metadata instance
        metadata = WCAOnPremMetaData(config)

        # Verify session was created
        self.assertIsInstance(metadata.session, requests.Session)

        # Verify session has HTTPS adapter
        https_adapter = metadata.session.get_adapter("https://example.com")
        self.assertIsInstance(https_adapter, requests.adapters.HTTPAdapter)

    def test_multiple_wca_instances_ssl_independence(self):
        """Test that multiple WCA instances have independent SSL configurations."""
        config1 = self._create_mock_config(verify_ssl=True)
        config2 = self._create_mock_config(verify_ssl=False)

        with patch("ssl.create_default_context") as mock_ssl_context:
            mock_ssl_context.return_value = Mock()

            # Create two metadata instances
            metadata1 = WCAOnPremMetaData(config1)
            metadata2 = WCAOnPremMetaData(config2)

            # Verify they have independent sessions
            self.assertIsNot(metadata1.session, metadata2.session)
            self.assertIsInstance(metadata1.session, requests.Session)
            self.assertIsInstance(metadata2.session, requests.Session)

            # Verify SSL was only set up for the first instance (verify_ssl=True)
            self.assertEqual(mock_ssl_context.call_count, 1)

    def test_ssl_context_error_handling(self):
        """Test error handling in SSL context setup."""
        config = self._create_mock_config(verify_ssl=True)

        with patch("ssl.create_default_context", side_effect=ssl.SSLError("SSL error")):
            # Should still create the metadata instance even if SSL setup fails
            with self.assertRaises(ssl.SSLError):
                WCAOnPremMetaData(config)


class TestWCASSLConfigurationIntegration(SimpleTestCase):
    """Integration tests for WCA SSL configuration."""

    def test_wca_ssl_with_real_session(self):
        """Test WCA SSL configuration with real session object."""
        config = Mock(spec=WCAOnPremConfiguration)
        config.verify_ssl = True
        config.retry_count = 3
        config.timeout = 30
        config.username = "test_user"
        config.api_key = "test_api_key"
        config.health_check_api_key = "test_health_key"
        config.health_check_model_id = "test_model"

        # Create metadata instance with real session
        metadata = WCAOnPremMetaData(config)

        # Verify session configuration
        self.assertIsInstance(metadata.session, requests.Session)

        # Verify HTTPS adapter is configured
        https_adapter = metadata.session.get_adapter("https://example.com")
        self.assertIsInstance(https_adapter, requests.adapters.HTTPAdapter)

    def test_ssl_verification_configuration(self):
        """Test SSL verification configuration for different settings."""
        test_cases = [
            (True, "SSL verification should be enabled"),
            (False, "SSL verification should be disabled"),
        ]

        for verify_ssl, description in test_cases:
            with self.subTest(verify_ssl=verify_ssl, msg=description):
                config = Mock(spec=WCAOnPremConfiguration)
                config.verify_ssl = verify_ssl
                config.retry_count = 3
                config.timeout = 30
                config.username = "test_user"
                config.api_key = "test_api_key"
                config.health_check_api_key = "test_health_key"
                config.health_check_model_id = "test_model"

                metadata = WCAOnPremMetaData(config)

                # Verify metadata was created successfully
                self.assertIsInstance(metadata.session, requests.Session)
                self.assertEqual(metadata.retries, 3)
                self.assertEqual(metadata._timeout, 30)

    def test_task_gen_timeout_functionality(self):
        """Test task generation timeout calculation."""
        config = Mock(spec=WCAOnPremConfiguration)
        config.verify_ssl = True
        config.retry_count = 3
        config.timeout = 10
        config.username = "test_user"
        config.api_key = "test_api_key"
        config.health_check_api_key = "test_health_key"
        config.health_check_model_id = "test_model"

        metadata = WCAOnPremMetaData(config)

        # Test timeout calculations
        self.assertEqual(metadata.task_gen_timeout(1), 10)
        self.assertEqual(metadata.task_gen_timeout(3), 30)
        self.assertEqual(metadata.task_gen_timeout(0), 0)

    def test_timeout_none_handling(self):
        """Test handling when timeout is None."""
        config = Mock(spec=WCAOnPremConfiguration)
        config.verify_ssl = True
        config.retry_count = 3
        config.timeout = None
        config.username = "test_user"
        config.api_key = "test_api_key"
        config.health_check_api_key = "test_health_key"
        config.health_check_model_id = "test_model"

        metadata = WCAOnPremMetaData(config)

        # Test timeout calculations with None
        self.assertIsNone(metadata.task_gen_timeout(1))
        self.assertIsNone(metadata.task_gen_timeout(5))

    def test_clean_ssl_environment_context_manager(self):
        """Test the SSL environment context manager functionality."""
        # Create temporary certificate files
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".crt") as temp_ca:
            temp_ca.write("-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----")
            temp_ca_path = temp_ca.name

        try:
            # Set up SSL environment pollution
            os.environ["REQUESTS_CA_BUNDLE"] = temp_ca_path
            os.environ["SSL_CERT_FILE"] = temp_ca_path

            config = Mock(spec=WCAOnPremConfiguration)
            config.verify_ssl = True
            config.retry_count = 3
            config.timeout = 30
            config.username = "test_user"
            config.api_key = "test_api_key"
            config.health_check_api_key = "test_health_key"
            config.health_check_model_id = "test_model"

            metadata = WCAOnPremMetaData(config)

            # Verify environment variables are set before context
            self.assertEqual(os.environ.get("REQUESTS_CA_BUNDLE"), temp_ca_path)
            self.assertEqual(os.environ.get("SSL_CERT_FILE"), temp_ca_path)

            # Test context manager clears variables
            with metadata._clean_ssl_environment():
                self.assertIsNone(os.environ.get("REQUESTS_CA_BUNDLE"))
                self.assertIsNone(os.environ.get("SSL_CERT_FILE"))

            # Verify environment variables are restored after context
            self.assertEqual(os.environ.get("REQUESTS_CA_BUNDLE"), temp_ca_path)
            self.assertEqual(os.environ.get("SSL_CERT_FILE"), temp_ca_path)

        finally:
            # Clean up
            os.unlink(temp_ca_path)
            os.environ.pop("REQUESTS_CA_BUNDLE", None)
            os.environ.pop("SSL_CERT_FILE", None)
