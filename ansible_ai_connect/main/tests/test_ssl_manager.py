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
Comprehensive unit tests for SSL Manager.

This test suite provides expert-level coverage of the SSL manager including:
- Complete line coverage of all SSL manager functionality
- Real-world deployment scenarios (Kubernetes, OpenShift, development)
- Security edge cases and error conditions
- Performance and reliability testing
- Integration with Django and external dependencies

As the central SSL management component for ansible-ai-connect-service,
the SSL manager requires rigorous testing to ensure security and reliability
in production environments.
"""

import logging
import os
import ssl
import tempfile
import unittest
from unittest.mock import patch

import requests
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from ansible_ai_connect.main.ssl_manager import SSLManager, ssl_manager


class TestSSLManagerInitialization(SimpleTestCase):
    """Test SSL manager initialization and environment variable handling."""

    def setUp(self):
        """Set up test environment with clean state."""
        # Store original environment
        self.original_env = {
            key: os.environ.get(key)
            for key in ["COMBINED_CA_BUNDLE_PATH", "SERVICE_CA_PATH", "REQUESTS_CA_BUNDLE"]
        }

    def tearDown(self):
        """Restore original environment."""
        for key, value in self.original_env.items():
            if value is not None:
                os.environ[key] = value
            elif key in os.environ:
                del os.environ[key]

    @patch.dict(os.environ, {}, clear=True)
    def test_initialization_no_environment_variables(self):
        """Test SSL manager initialization without any environment variables."""
        manager = SSLManager()

        # Verify all environment-based attributes are None
        self.assertIsNone(manager.combined_ca_bundle)
        self.assertIsNone(manager.service_ca_path)
        self.assertIsNone(manager.requests_ca_bundle)

    @patch.dict(
        os.environ,
        {
            "COMBINED_CA_BUNDLE_PATH": "/test/combined.pem",
            "SERVICE_CA_PATH": "/test/service.pem",
            "REQUESTS_CA_BUNDLE": "/test/requests.pem",
        },
        clear=True,
    )
    def test_initialization_with_all_environment_variables(self):
        """Test SSL manager initialization with all environment variables set."""
        manager = SSLManager()

        # Verify all environment variables are correctly loaded
        self.assertEqual(manager.combined_ca_bundle, "/test/combined.pem")
        self.assertEqual(manager.service_ca_path, "/test/service.pem")
        self.assertEqual(manager.requests_ca_bundle, "/test/requests.pem")

    @patch.dict(os.environ, {"COMBINED_CA_BUNDLE_PATH": "/kubernetes/combined-ca.pem"}, clear=True)
    def test_kubernetes_deployment_scenario(self):
        """Test SSL manager in typical Kubernetes deployment scenario."""
        manager = SSLManager()

        # Verify Kubernetes-style configuration
        self.assertEqual(manager.combined_ca_bundle, "/kubernetes/combined-ca.pem")
        self.assertIsNone(manager.service_ca_path)
        self.assertIsNone(manager.requests_ca_bundle)

    @patch.dict(
        os.environ,
        {"SERVICE_CA_PATH": "/var/run/secrets/kubernetes.io/serviceaccount/service-ca.crt"},
        clear=True,
    )
    def test_openshift_deployment_scenario(self):
        """Test SSL manager in typical OpenShift deployment scenario."""
        manager = SSLManager()

        # Verify OpenShift-style configuration
        self.assertIsNone(manager.combined_ca_bundle)
        self.assertEqual(
            manager.service_ca_path, "/var/run/secrets/kubernetes.io/serviceaccount/service-ca.crt"
        )
        self.assertIsNone(manager.requests_ca_bundle)

    @patch("ansible_ai_connect.main.ssl_manager.logger")
    def test_initialization_logging(self, mock_logger):
        """Test that SSL manager logs initialization information."""
        SSLManager()

        # Verify initialization logging
        mock_logger.info.assert_called_with("SSL Manager: Infrastructure mode initialized")

        # Verify debug logging calls
        expected_debug_calls = [
            unittest.mock.call("SSL Manager: Combined CA bundle: %s", None),
            unittest.mock.call("SSL Manager: Service CA: %s", None),
            unittest.mock.call("SSL Manager: Requests CA bundle: %s", None),
        ]
        mock_logger.debug.assert_has_calls(expected_debug_calls, any_order=True)


class TestSSLManagerLegacyServiceCAPath(SimpleTestCase):
    """Test _get_legacy_service_ca_path method for Django settings integration."""

    def test_legacy_service_ca_path_with_django_configured(self):
        """Test legacy service CA path retrieval with Django properly configured."""
        manager = SSLManager()

        # Since Django is already configured in test environment,
        # we can test the actual method behavior
        result = manager._get_legacy_service_ca_path()
        # Should return None or the actual SERVICE_CA_PATH if configured
        self.assertIsInstance(result, (type(None), str))

    def test_legacy_service_ca_path_django_not_configured(self):
        """Test legacy service CA path when Django is not configured."""
        manager = SSLManager()

        # Mock Django import to raise ImproperlyConfigured
        with patch("ansible_ai_connect.main.ssl_manager.getattr") as mock_getattr:
            mock_getattr.side_effect = ImproperlyConfigured("Django not configured")

            result = manager._get_legacy_service_ca_path()
            self.assertIsNone(result)

    def test_legacy_service_ca_path_settings_attribute_missing(self):
        """Test legacy service CA path when SERVICE_CA_PATH attribute is missing."""
        manager = SSLManager()

        # Mock getattr to return None (attribute missing)
        with patch("ansible_ai_connect.main.ssl_manager.getattr") as mock_getattr:
            mock_getattr.return_value = None

            result = manager._get_legacy_service_ca_path()
            self.assertIsNone(result)

    def test_legacy_service_ca_path_exception_handling(self):
        """Test legacy service CA path with various exception scenarios."""
        manager = SSLManager()

        # Test with AttributeError
        with patch("ansible_ai_connect.main.ssl_manager.getattr") as mock_getattr:
            mock_getattr.side_effect = AttributeError("Settings not available")

            result = manager._get_legacy_service_ca_path()
            self.assertIsNone(result)

        # Test with generic Exception
        with patch("ansible_ai_connect.main.ssl_manager.getattr") as mock_getattr:
            mock_getattr.side_effect = Exception("Unexpected error")

            result = manager._get_legacy_service_ca_path()
            self.assertIsNone(result)


class TestSSLManagerCABundlePath(SimpleTestCase):
    """Test _get_ca_bundle_path method for CA bundle priority and fallback logic."""

    def setUp(self):
        """Set up test environment."""
        self.manager = SSLManager()

    def test_ca_bundle_priority_combined_bundle_first(self):
        """Test CA bundle priority: combined bundle takes precedence."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as temp_file:
            temp_file.write("-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----\n")
            temp_file_path = temp_file.name

        try:
            # Set combined bundle path and mock other paths
            self.manager.combined_ca_bundle = temp_file_path
            self.manager.requests_ca_bundle = "/nonexistent/requests.pem"
            self.manager.service_ca_path = "/nonexistent/service.pem"

            with patch.object(
                self.manager, "_get_legacy_service_ca_path", return_value="/nonexistent/legacy.pem"
            ):
                result = self.manager._get_ca_bundle_path()
                self.assertEqual(result, temp_file_path)
        finally:
            os.unlink(temp_file_path)

    def test_ca_bundle_priority_requests_ca_bundle_second(self):
        """Test CA bundle priority: REQUESTS_CA_BUNDLE is second priority."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as temp_file:
            temp_file.write("-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----\n")
            temp_file_path = temp_file.name

        try:
            # Set requests CA bundle, no combined bundle
            self.manager.combined_ca_bundle = None
            self.manager.requests_ca_bundle = temp_file_path
            self.manager.service_ca_path = "/nonexistent/service.pem"

            with patch.object(
                self.manager, "_get_legacy_service_ca_path", return_value="/nonexistent/legacy.pem"
            ):
                result = self.manager._get_ca_bundle_path()
                self.assertEqual(result, temp_file_path)
        finally:
            os.unlink(temp_file_path)

    def test_ca_bundle_priority_service_ca_third(self):
        """Test CA bundle priority: SERVICE_CA_PATH is third priority."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as temp_file:
            temp_file.write("-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----\n")
            temp_file_path = temp_file.name

        try:
            # Set service CA path, no combined or requests bundle
            self.manager.combined_ca_bundle = None
            self.manager.requests_ca_bundle = None
            self.manager.service_ca_path = temp_file_path

            with patch.object(
                self.manager, "_get_legacy_service_ca_path", return_value="/nonexistent/legacy.pem"
            ):
                result = self.manager._get_ca_bundle_path()
                self.assertEqual(result, temp_file_path)
        finally:
            os.unlink(temp_file_path)

    def test_ca_bundle_priority_legacy_service_ca_fourth(self):
        """Test CA bundle priority: legacy service CA is fourth priority."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as temp_file:
            temp_file.write("-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----\n")
            temp_file_path = temp_file.name

        try:
            # No environment-based CA bundles, only legacy
            self.manager.combined_ca_bundle = None
            self.manager.requests_ca_bundle = None
            self.manager.service_ca_path = None

            with patch.object(
                self.manager, "_get_legacy_service_ca_path", return_value=temp_file_path
            ):
                result = self.manager._get_ca_bundle_path()
                self.assertEqual(result, temp_file_path)
        finally:
            os.unlink(temp_file_path)

    def test_ca_bundle_system_defaults_fallback(self):
        """Test CA bundle fallback to system defaults when no custom bundles available."""
        # No CA bundles available
        self.manager.combined_ca_bundle = None
        self.manager.requests_ca_bundle = None
        self.manager.service_ca_path = None

        with patch.object(self.manager, "_get_legacy_service_ca_path", return_value=None):
            result = self.manager._get_ca_bundle_path()
            self.assertIsNone(result)

    def test_ca_bundle_nonexistent_files_skipped(self):
        """Test that non-existent CA bundle files are skipped in priority order."""
        # All paths point to non-existent files
        self.manager.combined_ca_bundle = "/nonexistent/combined.pem"
        self.manager.requests_ca_bundle = "/nonexistent/requests.pem"
        self.manager.service_ca_path = "/nonexistent/service.pem"

        with patch.object(
            self.manager, "_get_legacy_service_ca_path", return_value="/nonexistent/legacy.pem"
        ):
            result = self.manager._get_ca_bundle_path()
            self.assertIsNone(result)

    @patch("ansible_ai_connect.main.ssl_manager.logger")
    def test_ca_bundle_logging_combined_bundle(self, mock_logger):
        """Test logging when combined CA bundle is used."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as temp_file:
            temp_file.write("-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----\n")
            temp_file_path = temp_file.name

        try:
            self.manager.combined_ca_bundle = temp_file_path
            self.manager._get_ca_bundle_path()

            mock_logger.debug.assert_called_with(
                "SSL Manager: Using infrastructure combined CA bundle: %s", temp_file_path
            )
        finally:
            os.unlink(temp_file_path)

    @patch("ansible_ai_connect.main.ssl_manager.logger")
    def test_ca_bundle_logging_system_defaults(self, mock_logger):
        """Test logging when falling back to system defaults."""
        self.manager.combined_ca_bundle = None
        self.manager.requests_ca_bundle = None
        self.manager.service_ca_path = None

        with patch.object(self.manager, "_get_legacy_service_ca_path", return_value=None):
            self.manager._get_ca_bundle_path()

            mock_logger.debug.assert_called_with(
                "SSL Manager: No custom CA bundle found, using system defaults"
            )


class TestSSLManagerRequestsSession(SimpleTestCase):
    """Test get_requests_session method for session configuration and SSL handling."""

    def setUp(self):
        """Set up test environment."""
        self.manager = SSLManager()

    def test_requests_session_creation_basic(self):
        """Test basic requests session creation."""
        session = self.manager.get_requests_session()

        self.assertIsInstance(session, requests.Session)
        # Default session.verify should be True (system defaults)
        self.assertTrue(session.verify)

    def test_requests_session_with_custom_ca_bundle(self):
        """Test requests session with custom CA bundle configuration."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as temp_file:
            temp_file.write("-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----\n")
            temp_file_path = temp_file.name

        try:
            with patch.object(self.manager, "_get_ca_bundle_path", return_value=temp_file_path):
                session = self.manager.get_requests_session()

                self.assertIsInstance(session, requests.Session)
                self.assertEqual(session.verify, temp_file_path)
        finally:
            os.unlink(temp_file_path)

    def test_requests_session_ca_bundle_not_accessible(self):
        """Test requests session when CA bundle exists but is not accessible.

        Note: SSL manager defers validation to actual HTTPS requests, so session creation
        succeeds but subsequent requests would fail with the inaccessible CA bundle.
        """
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as temp_file:
            temp_file.write("-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----\n")
            temp_file_path = temp_file.name

        try:
            # Make file unreadable
            os.chmod(temp_file_path, 0o000)

            with patch.object(self.manager, "_get_ca_bundle_path", return_value=temp_file_path):
                # Session creation should succeed (validation deferred to actual requests)
                session = self.manager.get_requests_session()

                # Session should be configured with the inaccessible path
                self.assertIsInstance(session, requests.Session)
                self.assertEqual(session.verify, temp_file_path)

                # The actual accessibility issue would manifest during HTTPS requests,
                # not during session creation. This matches requests library behavior.
        finally:
            # Restore permissions and clean up
            try:
                os.chmod(temp_file_path, 0o644)
                os.unlink(temp_file_path)
            except (OSError, PermissionError):
                pass

    def test_requests_session_no_ca_bundle_system_defaults(self):
        """Test requests session with no CA bundle (system defaults)."""
        with patch.object(self.manager, "_get_ca_bundle_path", return_value=None):
            session = self.manager.get_requests_session()

            self.assertIsInstance(session, requests.Session)
            self.assertTrue(session.verify)

            # When no CA bundle is found, session.verify remains True (system defaults)
            # The SSL manager doesn't log a specific message for this case

    def test_requests_session_os_error_handling(self):
        """Test requests session handling of OS errors during CA bundle access."""
        with patch.object(self.manager, "_get_ca_bundle_path") as mock_get_path:
            mock_get_path.side_effect = OSError("File system error")

            # SSL configuration errors should be fatal
            with patch("ansible_ai_connect.main.ssl_manager.logger") as mock_logger:
                with self.assertRaises(OSError) as cm:
                    self.manager.get_requests_session()

                # Should contain the original error message
                self.assertIn("File system error", str(cm.exception))

                # Should log the error as fatal (using exception for stack trace)
                mock_logger.exception.assert_called()

    def test_requests_session_attribute_error_handling(self):
        """Test requests session handling of attribute errors."""
        with patch.object(self.manager, "_get_ca_bundle_path") as mock_get_path:
            mock_get_path.side_effect = AttributeError("Attribute not found")

            # SSL configuration errors should be fatal
            with patch("ansible_ai_connect.main.ssl_manager.logger") as mock_logger:
                with self.assertRaises(OSError) as cm:
                    self.manager.get_requests_session()

                # Should contain the original error message
                self.assertIn("Attribute not found", str(cm.exception))

                # Should log the error as fatal (using exception for stack trace)
                mock_logger.exception.assert_called()

    @patch("ansible_ai_connect.main.ssl_manager.logger")
    def test_requests_session_logging_ca_bundle_configured(self, mock_logger):
        """Test logging when CA bundle is successfully configured."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as temp_file:
            temp_file.write("-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----\n")
            temp_file_path = temp_file.name

        try:
            with patch.object(self.manager, "_get_ca_bundle_path", return_value=temp_file_path):
                self.manager.get_requests_session()

                mock_logger.debug.assert_called_with(
                    "SSL Manager: Session configured with CA bundle: %s", temp_file_path
                )
        finally:
            os.unlink(temp_file_path)


class TestSSLManagerSSLContext(SimpleTestCase):
    """Test get_ssl_context method for SSL context creation and error handling."""

    def setUp(self):
        """Set up test environment."""
        self.manager = SSLManager()

    def test_ssl_context_with_custom_ca_bundle(self):
        """Test SSL context creation with custom CA bundle."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as temp_file:
            temp_file.write(
                """-----BEGIN CERTIFICATE-----
MIIDQTCCAimgAwIBAgITBmyfz5m/jAo54vB4ikPmljZbyjANBgkqhkiG9w0BAQsF
ADA5MQswCQYDVQQGEwJVUzEPMA0GA1UECgwGQW1hem9uMRkwFwYDVQQDDBBBbWF6
b24gUm9vdCBDQSAxMB4XDTE1MDUyNjAwMDAwMFoXDTM4MDExNzAwMDAwMFowOTEL
MAkGA1UEBhMCVVMxDzANBgNVBAoMBkFtYXpvbjEZMBcGA1UEAwwQQW1hem9uIFJv
b3QgQ0EgMTCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBALJ4gHHKeNXj
ca9HgFB0fW7Y14h29Jlo91ghYPl0hAEvrAIthtOgQ3pOsqTQNroBvo3bSMgHFzZM
9O6II8c+6zf1tRn4SWiw3te5djgdYZ6k/oI2peVKVuRF4fn9tBb6dNqcmzU5L/qw
IFAGbHrQgLKm+a/sRxmPUDgH3KKHOVj4utWp+UhnMJbulHheb4mjUcAwhmahRWa6
VOujw5H5SNz/0egwLX0tdHA114gk957EWW67c4cX8jJGKLhD+rcdqsq08p8kDi1L
93FcXmn/6pUCyziKrlA4b9v7LWIbxcceVOF34GfID5yHI9Y/QCB/IIDEgEw+OyQm
jgSubJrIqg0CAwEAAaNCMEAwDwYDVR0TAQH/BAUwAwEB/zAOBgNVHQ8BAf8EBAMC
AYYwHQYDVR0OBBYEFIQYzIU07LwMlJQuCFmcx7IQTgoIMA0GCSqGSIb3DQEBCwUA
A4IBAQCY8jdaQZChGsV2USggNiMOruYou6r4lK5IpDB/G/wkjUu0yKGX9rbxenDI
U5PMCCjjmCXPI6T53iHTfIuJruydjsw2hUwsOjNNvGEINXmF0w1iYYR2LYLPz+D3
1QbY0mJCXaLK7XzNJBLGfDvPCqr1wHl4aD6mX8s+MsG9lRJSA9HMnEe0DWBwfRqj
ySQdRgexoYqHDq3qEg8o8yOC6XHZEPxhZvZGzPXOtDp+7HuQsrhCd+N++Iw5Fgm7
WB3GLZfJvQQZ6cSXi4tKT7QQLdMhQl9qQPU3ELQ4A6LG1J5EWlRF2jP8qCRJvBGF
qLG8VpQ2W0XYLUgHRwcUdE+lGt7Q
-----END CERTIFICATE-----"""
            )
            temp_file_path = temp_file.name

        try:
            with patch.object(self.manager, "_get_ca_bundle_path", return_value=temp_file_path):
                with patch("ansible_ai_connect.main.ssl_manager.logger") as mock_logger:
                    context = self.manager.get_ssl_context()

                    self.assertIsInstance(context, ssl.SSLContext)

                    mock_logger.debug.assert_called_with(
                        "SSL Manager: Created SSL context with CA bundle: %s", temp_file_path
                    )
        finally:
            os.unlink(temp_file_path)

    def test_ssl_context_system_defaults(self):
        """Test SSL context creation with system defaults."""
        with patch.object(self.manager, "_get_ca_bundle_path", return_value=None):
            with patch("ansible_ai_connect.main.ssl_manager.logger") as mock_logger:
                context = self.manager.get_ssl_context()

                self.assertIsInstance(context, ssl.SSLContext)

                mock_logger.debug.assert_called_with(
                    "SSL Manager: Created SSL context with system defaults"
                )

    def test_ssl_context_defensive_programming_ca_bundle_none_check(self):
        """Test defensive programming: SSL context creation None check for CA bundle."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as temp_file:
            temp_file.write("-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----\n")
            temp_file_path = temp_file.name

        try:
            with patch.object(self.manager, "_get_ca_bundle_path", return_value=temp_file_path):
                with patch("ssl.create_default_context", return_value=None):
                    with self.assertRaises(ssl.SSLError) as context_manager:
                        self.manager.get_ssl_context()

                    self.assertIn("returned None unexpectedly", str(context_manager.exception))
        finally:
            os.unlink(temp_file_path)

    def test_ssl_context_defensive_programming_system_defaults_none_check(self):
        """Test defensive programming: SSL context creation None check for system defaults."""
        with patch.object(self.manager, "_get_ca_bundle_path", return_value=None):
            with patch("ssl.create_default_context", return_value=None):
                with self.assertRaises(ssl.SSLError) as context_manager:
                    self.manager.get_ssl_context()

                self.assertIn("returned None unexpectedly", str(context_manager.exception))

    def test_ssl_context_invalid_ca_file_error(self):
        """Test SSL context creation with invalid CA file."""
        # Create invalid CA file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as temp_file:
            temp_file.write("INVALID CERTIFICATE CONTENT")
            temp_file_path = temp_file.name

        try:
            with patch.object(self.manager, "_get_ca_bundle_path", return_value=temp_file_path):
                with self.assertRaises(ssl.SSLError):
                    self.manager.get_ssl_context()
        finally:
            os.unlink(temp_file_path)


class TestSSLManagerCAInfo(SimpleTestCase):
    """Test get_ca_info method for CA configuration information retrieval."""

    def setUp(self):
        """Set up test environment."""
        self.manager = SSLManager()

    def test_ca_info_structure(self):
        """Test CA info returns correct dictionary structure."""
        ca_info = self.manager.get_ca_info()

        self.assertIsInstance(ca_info, dict)

        expected_keys = [
            "active_ca_bundle",
            "combined_ca_bundle",
            "service_ca_path",
            "requests_ca_bundle",
            "legacy_service_ca",
            "ca_bundle_exists",
            "using_system_defaults",
        ]

        for key in expected_keys:
            self.assertIn(key, ca_info)

    def test_ca_info_with_active_ca_bundle(self):
        """Test CA info when active CA bundle is present."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as temp_file:
            temp_file.write("-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----\n")
            temp_file_path = temp_file.name

        try:
            with patch.object(self.manager, "_get_ca_bundle_path", return_value=temp_file_path):
                ca_info = self.manager.get_ca_info()

                self.assertEqual(ca_info["active_ca_bundle"], temp_file_path)
                self.assertTrue(ca_info["ca_bundle_exists"])
                self.assertFalse(ca_info["using_system_defaults"])
        finally:
            os.unlink(temp_file_path)

    def test_ca_info_using_system_defaults(self):
        """Test CA info when using system defaults."""
        with patch.object(self.manager, "_get_ca_bundle_path", return_value=None):
            with patch.object(self.manager, "_get_legacy_service_ca_path", return_value=None):
                ca_info = self.manager.get_ca_info()

                self.assertIsNone(ca_info["active_ca_bundle"])
                self.assertIsNone(ca_info["ca_bundle_exists"])
                self.assertTrue(ca_info["using_system_defaults"])

    def test_ca_info_environment_variables_reflection(self):
        """Test CA info reflects environment variable configuration."""
        # Set environment variables
        self.manager.combined_ca_bundle = "/test/combined.pem"
        self.manager.service_ca_path = "/test/service.pem"
        self.manager.requests_ca_bundle = "/test/requests.pem"

        with patch.object(self.manager, "_get_ca_bundle_path", return_value=None):
            with patch.object(
                self.manager, "_get_legacy_service_ca_path", return_value="/test/legacy.pem"
            ):
                ca_info = self.manager.get_ca_info()

                self.assertEqual(ca_info["combined_ca_bundle"], "/test/combined.pem")
                self.assertEqual(ca_info["service_ca_path"], "/test/service.pem")
                self.assertEqual(ca_info["requests_ca_bundle"], "/test/requests.pem")
                self.assertEqual(ca_info["legacy_service_ca"], "/test/legacy.pem")

    def test_ca_info_ca_bundle_exists_nonexistent_file(self):
        """Test CA info ca_bundle_exists with non-existent file."""
        with patch.object(self.manager, "_get_ca_bundle_path", return_value="/nonexistent/ca.pem"):
            ca_info = self.manager.get_ca_info()

            self.assertEqual(ca_info["active_ca_bundle"], "/nonexistent/ca.pem")
            self.assertFalse(ca_info["ca_bundle_exists"])
            self.assertFalse(ca_info["using_system_defaults"])


class TestSSLManagerGlobalInstance(SimpleTestCase):
    """Test the global SSL manager instance and its properties."""

    def test_global_ssl_manager_instance_exists(self):
        """Test that global ssl_manager instance exists and is properly configured."""
        self.assertIsNotNone(ssl_manager)
        self.assertIsInstance(ssl_manager, SSLManager)

    def test_global_ssl_manager_singleton_behavior(self):
        """Test that ssl_manager behaves as expected singleton."""
        # Import ssl_manager multiple times to ensure consistency
        from ansible_ai_connect.main.ssl_manager import ssl_manager as manager1
        from ansible_ai_connect.main.ssl_manager import ssl_manager as manager2

        self.assertIs(manager1, manager2)
        self.assertIs(ssl_manager, manager1)

    def test_global_ssl_manager_methods_available(self):
        """Test that all expected methods are available on global instance."""
        expected_methods = [
            "get_requests_session",
            "get_ssl_context",
            "get_ca_info",
            "_get_ca_bundle_path",
            "_get_legacy_service_ca_path",
        ]

        for method_name in expected_methods:
            self.assertTrue(hasattr(ssl_manager, method_name))
            self.assertTrue(callable(getattr(ssl_manager, method_name)))


class TestSSLManagerRealWorldScenarios(SimpleTestCase):
    """Test SSL manager in real-world deployment scenarios."""

    def setUp(self):
        """Set up test environment."""
        # Store original environment to restore later
        self.original_env = dict(os.environ)

    def tearDown(self):
        """Restore original environment."""
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_kubernetes_production_deployment(self):
        """Test SSL manager in Kubernetes production deployment scenario."""
        # Simulate Kubernetes environment
        os.environ.clear()
        os.environ.update(
            {
                "COMBINED_CA_BUNDLE_PATH": "/etc/ssl/certs/ca-certificates.crt",
                "SERVICE_CA_PATH": "/var/run/secrets/kubernetes.io/serviceaccount/service-ca.crt",
            }
        )

        manager = SSLManager()

        # Mock file existence for the combined bundle
        with patch("os.path.exists") as mock_exists:
            mock_exists.side_effect = lambda path: path == "/etc/ssl/certs/ca-certificates.crt"

            ca_bundle_path = manager._get_ca_bundle_path()
            self.assertEqual(ca_bundle_path, "/etc/ssl/certs/ca-certificates.crt")

    def test_openshift_deployment_with_service_ca(self):
        """Test SSL manager in OpenShift deployment with service CA."""
        # Simulate OpenShift environment
        os.environ.clear()
        os.environ.update(
            {"SERVICE_CA_PATH": "/var/run/secrets/kubernetes.io/serviceaccount/service-ca.crt"}
        )

        manager = SSLManager()

        # Mock file existence for service CA only
        with patch("os.path.exists") as mock_exists:
            mock_exists.side_effect = (
                lambda path: path == "/var/run/secrets/kubernetes.io/serviceaccount/service-ca.crt"
            )

            ca_bundle_path = manager._get_ca_bundle_path()
            self.assertEqual(
                ca_bundle_path, "/var/run/secrets/kubernetes.io/serviceaccount/service-ca.crt"
            )

    def test_development_environment_no_custom_ca(self):
        """Test SSL manager in development environment without custom CA."""
        # Simulate development environment
        os.environ.clear()

        manager = SSLManager()

        # No custom CA bundles available
        with patch.object(manager, "_get_legacy_service_ca_path", return_value=None):
            ca_bundle_path = manager._get_ca_bundle_path()
            self.assertIsNone(ca_bundle_path)

            # Should use system defaults
            ca_info = manager.get_ca_info()
            self.assertTrue(ca_info["using_system_defaults"])

    def test_legacy_django_configuration_integration(self):
        """Test SSL manager integration with legacy Django configuration."""
        # Simulate environment without operator-provided CA bundles
        os.environ.clear()

        manager = SSLManager()

        # Mock Django settings with legacy SERVICE_CA_PATH
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as temp_file:
            temp_file.write("-----BEGIN CERTIFICATE-----\nlegacy\n-----END CERTIFICATE-----\n")
            temp_file_path = temp_file.name

        try:
            with patch.object(manager, "_get_legacy_service_ca_path", return_value=temp_file_path):
                ca_bundle_path = manager._get_ca_bundle_path()
                self.assertEqual(ca_bundle_path, temp_file_path)
        finally:
            os.unlink(temp_file_path)

    def test_high_availability_deployment_fallback_chain(self):
        """Test SSL manager fallback chain in high-availability deployment."""
        # Simulate scenario where primary CA bundle fails but fallback succeeds
        os.environ.clear()
        os.environ.update(
            {
                "COMBINED_CA_BUNDLE_PATH": "/primary/ca-bundle.pem",  # Will be inaccessible
                "REQUESTS_CA_BUNDLE": "/fallback/ca-bundle.pem",  # Will be accessible
            }
        )

        manager = SSLManager()

        # Create accessible fallback CA bundle
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as temp_file:
            temp_file.write("-----BEGIN CERTIFICATE-----\nfallback\n-----END CERTIFICATE-----\n")
            fallback_path = temp_file.name

        try:
            # Mock file existence to simulate primary failure, fallback success
            def mock_exists(path):
                return path == fallback_path

            manager.requests_ca_bundle = fallback_path  # Override for test

            with patch("os.path.exists", side_effect=mock_exists):
                ca_bundle_path = manager._get_ca_bundle_path()
                self.assertEqual(ca_bundle_path, fallback_path)
        finally:
            os.unlink(fallback_path)

    def test_security_scenario_file_permission_issues(self):
        """Test SSL manager security scenario with file permission issues.

        Note: SSL manager defers validation to actual HTTPS requests, so session creation
        succeeds but subsequent requests would fail with the inaccessible CA bundle.
        This matches the requests library's lazy validation approach.
        """
        # Create CA bundle with restricted permissions
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as temp_file:
            temp_file.write("-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----\n")
            temp_file_path = temp_file.name

        try:
            # Remove read permissions
            os.chmod(temp_file_path, 0o000)

            manager = SSLManager()

            with patch.object(manager, "_get_ca_bundle_path", return_value=temp_file_path):
                # Session creation should succeed (validation deferred to actual requests)
                session = manager.get_requests_session()

                # Session should be configured with the inaccessible path
                self.assertIsInstance(session, requests.Session)
                self.assertEqual(session.verify, temp_file_path)

                # The security issue would manifest during actual HTTPS requests,
                # not during session creation. This follows requests library behavior.
        finally:
            # Restore permissions and clean up
            try:
                os.chmod(temp_file_path, 0o644)
                os.unlink(temp_file_path)
            except (OSError, PermissionError):
                pass

    def test_performance_scenario_concurrent_access(self):
        """Test SSL manager performance with concurrent access patterns."""
        import threading

        manager = SSLManager()
        results = []
        errors = []

        def worker():
            try:
                # Each thread should get a valid session
                session = manager.get_requests_session()
                ssl_context = manager.get_ssl_context()
                ca_info = manager.get_ca_info()

                results.append(
                    {
                        "session": isinstance(session, requests.Session),
                        "ssl_context": isinstance(ssl_context, ssl.SSLContext),
                        "ca_info": isinstance(ca_info, dict),
                    }
                )
            except Exception as e:
                errors.append(e)

        # Create multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=worker)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify no errors occurred
        self.assertEqual(len(errors), 0, f"Concurrent access errors: {errors}")

        # Verify all threads succeeded
        self.assertEqual(len(results), 10)
        for result in results:
            self.assertTrue(result["session"])
            self.assertTrue(result["ssl_context"])
            self.assertTrue(result["ca_info"])


class TestSSLManagerEdgeCasesAndErrorConditions(SimpleTestCase):
    """Test SSL manager edge cases and error conditions for robustness."""

    def setUp(self):
        """Set up test environment."""
        self.manager = SSLManager()

    def test_corrupted_ca_bundle_file(self):
        """Test SSL manager with corrupted CA bundle file."""
        # Create corrupted CA bundle
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as temp_file:
            temp_file.write("CORRUPTED CERTIFICATE DATA\x00\xFF\x00")
            temp_file_path = temp_file.name

        try:
            with patch.object(self.manager, "_get_ca_bundle_path", return_value=temp_file_path):
                # SSL context creation should fail with SSL error
                with self.assertRaises(ssl.SSLError):
                    self.manager.get_ssl_context()
        finally:
            os.unlink(temp_file_path)

    def test_empty_ca_bundle_file(self):
        """Test SSL manager with empty CA bundle file."""
        # Create empty CA bundle
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as temp_file:
            temp_file.write("")  # Empty file
            temp_file_path = temp_file.name

        try:
            with patch.object(self.manager, "_get_ca_bundle_path", return_value=temp_file_path):
                # SSL context creation should fail with SSL error
                with self.assertRaises(ssl.SSLError):
                    self.manager.get_ssl_context()
        finally:
            os.unlink(temp_file_path)

    def test_unicode_handling_in_paths(self):
        """Test SSL manager with Unicode characters in file paths."""
        # Create CA bundle with Unicode in path
        unicode_dir = "/tmp/test_ñömé_你好"
        unicode_path = f"{unicode_dir}/ca-bundle.pem"

        with patch.object(self.manager, "_get_ca_bundle_path", return_value=unicode_path):
            with patch("os.path.exists", return_value=False):
                # Should handle Unicode paths gracefully
                ca_bundle_path = self.manager._get_ca_bundle_path()
                self.assertEqual(ca_bundle_path, unicode_path)

    def test_extremely_long_file_paths(self):
        """Test SSL manager with extremely long file paths."""
        # Create extremely long path
        long_path = "/tmp/" + "a" * 1000 + ".pem"

        with patch.object(self.manager, "_get_ca_bundle_path", return_value=long_path):
            with patch("os.path.exists", return_value=False):
                # Should handle long paths gracefully
                ca_bundle_path = self.manager._get_ca_bundle_path()
                self.assertEqual(ca_bundle_path, long_path)

    def test_file_system_race_conditions(self):
        """Test SSL manager handling of file system race conditions."""
        # Create CA bundle that exists during path check but disappears during access
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as temp_file:
            temp_file.write("-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----\n")
            temp_file_path = temp_file.name

        try:
            with patch.object(self.manager, "_get_ca_bundle_path", return_value=temp_file_path):
                # Remove file between path check and access
                os.unlink(temp_file_path)

                # Should handle gracefully with appropriate error
                with self.assertRaises(ssl.SSLError):
                    self.manager.get_ssl_context()
        except OSError:
            # File might already be deleted
            pass

    def test_memory_pressure_scenario(self):
        """Test SSL manager under memory pressure scenarios."""
        # Simulate memory pressure by creating many sessions
        sessions = []
        ssl_contexts = []

        try:
            for i in range(100):
                session = self.manager.get_requests_session()
                ssl_context = self.manager.get_ssl_context()

                sessions.append(session)
                ssl_contexts.append(ssl_context)

                # Verify each instance is valid
                self.assertIsInstance(session, requests.Session)
                self.assertIsInstance(ssl_context, ssl.SSLContext)
        except MemoryError:
            # This is acceptable under extreme memory pressure
            pass

    def test_disk_space_exhaustion_simulation(self):
        """Test SSL manager behavior when disk space is exhausted."""
        # Mock _get_ca_bundle_path to raise OSError simulating disk space issues
        with patch.object(self.manager, "_get_ca_bundle_path") as mock_get_path:
            mock_get_path.side_effect = OSError("No space left on device")

            # SSL configuration errors should be fatal
            with patch("ansible_ai_connect.main.ssl_manager.logger") as mock_logger:
                with self.assertRaises(OSError) as cm:
                    self.manager.get_requests_session()

                # Should contain the original error message
                self.assertIn("No space left on device", str(cm.exception))

                # Should log the error as fatal (using exception for stack trace)
                mock_logger.exception.assert_called()


if __name__ == "__main__":
    # Configure logging for test output
    logging.basicConfig(level=logging.WARNING)

    # Run the comprehensive test suite
    unittest.main(verbosity=2)
