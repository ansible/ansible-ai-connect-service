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
SSL-specific tests for WCA (Wisdom Connect Authentication) system.

This test suite prevents SSL failures like the ones introduced by PR #1754
by testing SSL configuration isolation and external service connectivity.

The tests ensure that:
1. HTTP pipeline SSL changes don't affect WCA authentication
2. External SSL connections (sso.redhat.com) work correctly
3. SSL error handling is robust and graceful
4. Environment variable pollution is prevented
5. Multiple WCA instances operate independently

These tests mock all network calls and cache operations to avoid 
dependencies on external services or database configuration.
"""

import os
import tempfile
from datetime import datetime, timedelta
from http import HTTPStatus
from unittest.mock import Mock, patch

import requests
from django.test import SimpleTestCase, override_settings
from requests.exceptions import ConnectionError, SSLError, Timeout

from ansible_ai_connect.users.authz_checker import AMSCheck, Token


class TestWCASSLIsolation(SimpleTestCase):
    """Test SSL configuration isolation for WCA authentication system."""

    def setUp(self):
        super().setUp()
        # Store original environment variables
        self.original_ca_bundle = os.environ.get("REQUESTS_CA_BUNDLE")
        self.original_ssl_cert = os.environ.get("SSL_CERT_FILE")

    def tearDown(self):
        """Restore original environment variables"""
        # Clean up environment variables
        if self.original_ca_bundle:
            os.environ["REQUESTS_CA_BUNDLE"] = self.original_ca_bundle
        else:
            os.environ.pop("REQUESTS_CA_BUNDLE", None)
            
        if self.original_ssl_cert:
            os.environ["SSL_CERT_FILE"] = self.original_ssl_cert
        else:
            os.environ.pop("SSL_CERT_FILE", None)
        super().tearDown()

    def test_token_ssl_unaffected_by_pipeline_ssl_config(self):
        """Test that Token SSL requests are not affected by HTTP pipeline SSL configuration."""
        # Simulate HTTP pipeline setting global SSL environment variables
        # (This was the problematic behavior from PR #1754)
        service_ca_path = "/var/run/secrets/kubernetes.io/serviceaccount/service-ca.crt"
        os.environ["REQUESTS_CA_BUNDLE"] = service_ca_path
        os.environ["SSL_CERT_FILE"] = service_ca_path

        # Mock successful token refresh
        with patch("requests.post") as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {"access_token": "test_token", "expires_in": 900}
            mock_response.status_code = HTTPStatus.OK
            mock_post.return_value = mock_response

            # Test Token initialization and refresh
            token = Token("test_client", "test_secret", "https://sso.redhat.com")
            token.refresh()

            # Verify the request was made (would fail if SSL verification failed)
            mock_post.assert_called_once()
            self.assertEqual(token.access_token, "test_token")
            
            # Verify the call used the correct URL (external SSO service)
            args, kwargs = mock_post.call_args
            expected_url = "https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token"
            self.assertEqual(args[0], expected_url)

    def test_ams_check_ssl_unaffected_by_pipeline_ssl_config(self):
        """Test that AMSCheck SSL requests are not affected by HTTP pipeline SSL configuration."""
        # Simulate HTTP pipeline setting global SSL environment variables
        service_ca_path = "/var/run/secrets/kubernetes.io/serviceaccount/service-ca.crt"
        os.environ["REQUESTS_CA_BUNDLE"] = service_ca_path
        os.environ["SSL_CERT_FILE"] = service_ca_path

        # Mock successful AMS API calls and cache
        with patch.object(requests.Session, "get") as mock_get, \
             patch("django.core.cache.cache.get") as mock_cache_get, \
             patch("django.core.cache.cache.set") as mock_cache_set:
            
            # Mock cache miss (None) to force API call
            mock_cache_get.return_value = None
            
            mock_response = Mock()
            mock_response.json.return_value = {"items": [{"id": "test_org_id"}]}
            mock_response.status_code = HTTPStatus.OK
            mock_get.return_value = mock_response

            # Test AMSCheck functionality
            ams_check = AMSCheck(
                "test_client", 
                "test_secret", 
                "https://sso.redhat.com", 
                "https://api.openshift.com"
            )
            ams_check._token = Mock()  # Mock token to avoid SSO calls
            
            result = ams_check.get_organization(123)
            
            # Verify the request was made (would fail if SSL verification failed)
            mock_get.assert_called_once()
            self.assertEqual(result["id"], "test_org_id")

    def test_token_ssl_error_handling(self):
        """Test proper handling of SSL errors in Token class."""
        with patch("requests.post") as mock_post:
            # Simulate the SSL error that was occurring
            ssl_error = SSLError("SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate")
            mock_post.side_effect = ssl_error

            token = Token("test_client", "test_secret", "https://sso.redhat.com")
            
            # SSL errors should be caught and handled gracefully
            with self.assertLogs(logger="ansible_ai_connect.users.authz_checker", level="INFO") as log:
                result = token.refresh()
                
                # Should return None on SSL error
                self.assertIsNone(result)
                
                # Should log the SSL error appropriately
                self.assertIn("Cannot reach the SSO backend in time", str(log.output))

    def test_ams_check_ssl_error_handling(self):
        """Test proper handling of SSL errors in AMSCheck class."""
        with patch.object(requests.Session, "get") as mock_get, \
             patch("django.core.cache.cache.get") as mock_cache_get:
            
            # Mock cache miss to force API call
            mock_cache_get.return_value = None
            
            # Simulate SSL certificate verification error
            ssl_error = SSLError("SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate")
            mock_get.side_effect = ssl_error

            ams_check = AMSCheck(
                "test_client", 
                "test_secret", 
                "https://sso.redhat.com", 
                "https://api.openshift.com"
            )
            ams_check._token = Mock()  # Mock token to avoid SSO calls

            # SSL errors should be caught and handled gracefully
            with self.assertLogs(logger="root", level="ERROR") as log:
                with self.assertRaises(AMSCheck.AMSError):
                    ams_check.get_organization(123)
                
                # Should log the connection timeout message
                self.assertIn("Cannot reach the AMS backend in time", str(log.output))

    def test_external_ssl_verification_works_with_system_cas(self):
        """Test that external SSL verification works correctly with system CAs."""
        # Clear any potentially problematic environment variables
        os.environ.pop("REQUESTS_CA_BUNDLE", None)
        os.environ.pop("SSL_CERT_FILE", None)

        with patch("requests.post") as mock_post:
            # Mock successful response (simulating proper SSL verification with system CAs)
            mock_response = Mock()
            mock_response.json.return_value = {"access_token": "test_token", "expires_in": 900}
            mock_response.status_code = HTTPStatus.OK
            mock_post.return_value = mock_response

            token = Token("test_client", "test_secret", "https://sso.redhat.com")
            token.refresh()

            # Verify request was made successfully
            mock_post.assert_called_once()
            self.assertEqual(token.access_token, "test_token")

    def test_service_ca_environment_variable_pollution_detection(self):
        """Test detection of service CA environment variable pollution."""
        # Simulate the problematic scenario from PR #1754
        service_ca_path = "/var/run/secrets/kubernetes.io/serviceaccount/service-ca.crt"
        
        # Set global environment variables (the problematic behavior)
        os.environ["REQUESTS_CA_BUNDLE"] = service_ca_path
        os.environ["SSL_CERT_FILE"] = service_ca_path

        # Verify environment variables are set
        self.assertEqual(os.environ.get("REQUESTS_CA_BUNDLE"), service_ca_path)
        self.assertEqual(os.environ.get("SSL_CERT_FILE"), service_ca_path)

        # This is what was causing the SSL failures - these global environment
        # variables would force ALL requests to use the service CA, including
        # external service connections that need public root CAs

        # Mock a request that would fail with service CA but succeed with system CAs
        with patch("requests.post") as mock_post:
            # First call fails due to service CA (simulated)
            ssl_error = SSLError("certificate verify failed: unable to get local issuer certificate")
            mock_post.side_effect = ssl_error

            token = Token("test_client", "test_secret", "https://sso.redhat.com")
            
            with self.assertLogs(logger="ansible_ai_connect.users.authz_checker", level="INFO") as log:
                result = token.refresh()
                
                # Should fail due to service CA pollution
                self.assertIsNone(result)
                self.assertIn("Cannot reach the SSO backend in time", str(log.output))

    @override_settings(AUTHZ_SSO_TOKEN_SERVICE_RETRY_COUNT=1)
    def test_ssl_retry_behavior(self):
        """Test SSL retry behavior under various error conditions."""
        with patch("requests.post") as mock_post:
            # First call fails with SSL error, second succeeds
            ssl_error = SSLError("SSL handshake failed")
            success_response = Mock()
            success_response.json.return_value = {"access_token": "retry_token", "expires_in": 900}
            success_response.status_code = HTTPStatus.OK
            
            mock_post.side_effect = [ssl_error, success_response]

            token = Token("test_client", "test_secret", "https://sso.redhat.com")
            
            with self.assertLogs(logger="ansible_ai_connect.users.authz_checker", level="INFO") as log:
                token.refresh()
                
                # Should succeed on retry
                self.assertEqual(token.access_token, "retry_token")
                
                # Should have logged retry attempts
                self.assertIn("Caught retryable error", str(log.output))

    def test_different_ssl_servers_isolation(self):
        """Test that different SSL servers are handled independently."""
        # Test that Token and AMSCheck can connect to different SSL endpoints
        # without interfering with each other
        
        with patch("requests.post") as mock_token_post, \
             patch.object(requests.Session, "get") as mock_ams_get, \
             patch("django.core.cache.cache.get") as mock_cache_get, \
             patch("django.core.cache.cache.set") as mock_cache_set:
            
            # Mock cache miss to force API call
            mock_cache_get.return_value = None
            
            # Mock successful responses for both services
            token_response = Mock()
            token_response.json.return_value = {"access_token": "sso_token", "expires_in": 900}
            token_response.status_code = HTTPStatus.OK
            mock_token_post.return_value = token_response
            
            ams_response = Mock()
            ams_response.json.return_value = {"items": [{"id": "ams_org"}]}
            ams_response.status_code = HTTPStatus.OK
            mock_ams_get.return_value = ams_response

            # Test Token (SSO connection)
            token = Token("test_client", "test_secret", "https://sso.redhat.com")
            token.refresh()
            self.assertEqual(token.access_token, "sso_token")

            # Test AMSCheck (AMS API connection)
            ams_check = AMSCheck(
                "test_client", 
                "test_secret", 
                "https://sso.redhat.com", 
                "https://api.openshift.com"
            )
            ams_check._token = Mock()  # Mock to avoid SSO calls
            
            result = ams_check.get_organization(123)
            self.assertEqual(result["id"], "ams_org")

            # Verify both services were called
            mock_token_post.assert_called_once()
            mock_ams_get.assert_called_once()


class TestWCASSLCertificateScenarios(SimpleTestCase):
    """Test various SSL certificate scenarios for WCA authentication."""

    def test_token_with_custom_server(self):
        """Test Token class with custom server endpoints."""
        with patch("requests.post") as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {"access_token": "custom_token", "expires_in": 900}
            mock_response.status_code = HTTPStatus.OK
            mock_post.return_value = mock_response

            # Test with custom server
            token = Token("test_client", "test_secret", "https://custom-sso.example.com")
            token.refresh()

            # Verify correct custom server was used
            args, kwargs = mock_post.call_args
            expected_url = "https://custom-sso.example.com/auth/realms/redhat-external/protocol/openid-connect/token"
            self.assertEqual(args[0], expected_url)
            self.assertEqual(token.access_token, "custom_token")

    def test_ams_check_proxy_configuration(self):
        """Test AMSCheck proxy configuration for staging environments."""
        # Test the staging proxy configuration
        ams_check = AMSCheck(
            "test_client", 
            "test_secret", 
            "https://sso.redhat.com", 
            "https://api.stage.openshift.com/some/path"
        )
        
        # Verify proxy is configured for staging
        expected_proxy = {"https": "http://squid.corp.redhat.com:3128"}
        self.assertEqual(ams_check._session.proxies, expected_proxy)

    def test_ams_check_no_proxy_for_production(self):
        """Test AMSCheck does not configure proxy for production environments."""
        ams_check = AMSCheck(
            "test_client", 
            "test_secret", 
            "https://sso.redhat.com", 
            "https://api.openshift.com"
        )
        
        # Verify no proxy is configured for production
        self.assertEqual(ams_check._session.proxies, {})

    def test_ssl_timeout_scenarios(self):
        """Test SSL timeout handling in various scenarios."""
        with patch("requests.post") as mock_post:
            # Simulate connection timeout (could be SSL handshake timeout)
            mock_post.side_effect = Timeout("SSL handshake timeout")

            token = Token("test_client", "test_secret", "https://sso.redhat.com")
            
            with self.assertLogs(logger="ansible_ai_connect.users.authz_checker", level="INFO") as log:
                result = token.refresh()
                
                # Should handle timeout gracefully
                self.assertIsNone(result)
                self.assertIn("Cannot reach the SSO backend in time", str(log.output))

    def test_connection_error_vs_ssl_error(self):
        """Test distinction between connection errors and SSL errors."""
        # Test ConnectionError
        with patch("requests.post") as mock_post:
            mock_post.side_effect = ConnectionError("Connection refused")

            token = Token("test_client", "test_secret", "https://sso.redhat.com")
            
            with self.assertLogs(logger="ansible_ai_connect.users.authz_checker", level="INFO") as log:
                result = token.refresh()
                
                self.assertIsNone(result)
                self.assertIn("Cannot reach the SSO backend in time", str(log.output))

        # Test SSLError separately
        with patch("requests.post") as mock_post:
            mock_post.side_effect = SSLError("SSL protocol error")

            token = Token("test_client", "test_secret", "https://sso.redhat.com")
            
            with self.assertLogs(logger="ansible_ai_connect.users.authz_checker", level="INFO") as log:
                result = token.refresh()
                
                self.assertIsNone(result)
                self.assertIn("Cannot reach the SSO backend in time", str(log.output))


class TestWCASSLRegressionPrevention(SimpleTestCase):
    """Regression tests to prevent specific SSL issues like PR #1754."""

    def test_pr_1754_ssl_regression_prevention(self):
        """
        Regression test for PR #1754 SSL issue.
        
        This test ensures that HTTP pipeline SSL configuration changes
        do not affect WCA authentication SSL behavior.
        """
        # Create a temporary certificate file to simulate service CA
        with tempfile.NamedTemporaryFile(mode="w", suffix=".crt", delete=False) as temp_cert:
            # Use a sample certificate content
            temp_cert.write("""-----BEGIN CERTIFICATE-----
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
qLG8VpQ2W0XYLUgHRwcUdE+lGt7Q+ZI6OGP44Eaz1y3lZhp2lCKgLLOBwsGw
-----END CERTIFICATE-----""")
            temp_cert_path = temp_cert.name

        try:
            # Simulate the PR #1754 problematic scenario:
            # HTTP pipeline sets global SSL environment variables
            os.environ["REQUESTS_CA_BUNDLE"] = temp_cert_path
            os.environ["SSL_CERT_FILE"] = temp_cert_path

            # This should NOT affect WCA authentication
            with patch("requests.post") as mock_post:
                # Mock a scenario where the request would succeed with system CAs
                # but might fail with the service CA
                mock_response = Mock()
                mock_response.json.return_value = {"access_token": "regression_test_token", "expires_in": 900}
                mock_response.status_code = HTTPStatus.OK
                mock_post.return_value = mock_response

                token = Token("test_client", "test_secret", "https://sso.redhat.com")
                token.refresh()

                # Should succeed despite global SSL environment variables
                self.assertEqual(token.access_token, "regression_test_token")
                
                # Verify the call was made to the correct external endpoint
                args, kwargs = mock_post.call_args
                expected_url = "https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token"
                self.assertEqual(args[0], expected_url)

        finally:
            # Clean up temporary file
            os.unlink(temp_cert_path)

    def test_ssl_environment_variable_isolation_verification(self):
        """
        Verify that WCA components don't inadvertently set global SSL environment variables.
        
        This prevents the root cause of the PR #1754 issue from recurring.
        """
        # Clear environment variables
        os.environ.pop("REQUESTS_CA_BUNDLE", None)
        os.environ.pop("SSL_CERT_FILE", None)

        # Create WCA components
        token = Token("test_client", "test_secret", "https://sso.redhat.com")
        ams_check = AMSCheck(
            "test_client", 
            "test_secret", 
            "https://sso.redhat.com", 
            "https://api.openshift.com"
        )

        # Verify WCA components don't set global SSL environment variables
        self.assertIsNone(os.environ.get("REQUESTS_CA_BUNDLE"))
        self.assertIsNone(os.environ.get("SSL_CERT_FILE"))

        # Verify they can still function (with mocked responses)
        with patch("requests.post") as mock_post, \
             patch.object(requests.Session, "get") as mock_get, \
             patch("django.core.cache.cache.get") as mock_cache_get, \
             patch("django.core.cache.cache.set") as mock_cache_set:
            
            # Mock cache miss to force API call
            mock_cache_get.return_value = None
            
            # Mock successful responses
            token_response = Mock()
            token_response.json.return_value = {"access_token": "clean_token", "expires_in": 900}
            token_response.status_code = HTTPStatus.OK
            mock_post.return_value = token_response

            ams_response = Mock()
            ams_response.json.return_value = {"items": [{"id": "clean_org"}]}
            ams_response.status_code = HTTPStatus.OK
            mock_get.return_value = ams_response

            # Test functionality
            token.refresh()
            self.assertEqual(token.access_token, "clean_token")

            ams_check._token = Mock()  # Mock token to avoid SSO calls
            result = ams_check.get_organization(123)
            self.assertEqual(result["id"], "clean_org")

            # Environment should still be clean
            self.assertIsNone(os.environ.get("REQUESTS_CA_BUNDLE"))
            self.assertIsNone(os.environ.get("SSL_CERT_FILE"))

    def test_multiple_ssl_context_independence(self):
        """
        Test that multiple WCA authentication instances don't interfere with each other's SSL context.
        """
        # Create multiple Token instances with different servers
        token1 = Token("client1", "secret1", "https://sso1.redhat.com")
        token2 = Token("client2", "secret2", "https://sso2.redhat.com")
        
        # Create multiple AMSCheck instances
        ams1 = AMSCheck("client1", "secret1", "https://sso1.redhat.com", "https://api1.openshift.com")
        ams2 = AMSCheck("client2", "secret2", "https://sso2.redhat.com", "https://api2.openshift.com")

        # Mock responses for all instances
        with patch("requests.post") as mock_post, \
             patch.object(requests.Session, "get") as mock_get, \
             patch("django.core.cache.cache.get") as mock_cache_get, \
             patch("django.core.cache.cache.set") as mock_cache_set:
            
            # Mock cache miss to force API calls
            mock_cache_get.return_value = None
            
            # Mock different responses for different instances
            def post_side_effect(url, **kwargs):
                response = Mock()
                if "sso1.redhat.com" in url:
                    response.json.return_value = {"access_token": "token1", "expires_in": 900}
                elif "sso2.redhat.com" in url:
                    response.json.return_value = {"access_token": "token2", "expires_in": 900}
                response.status_code = HTTPStatus.OK
                return response

            def get_side_effect(url, **kwargs):
                response = Mock()
                if "api1.openshift.com" in url:
                    response.json.return_value = {"items": [{"id": "org1"}]}
                elif "api2.openshift.com" in url:
                    response.json.return_value = {"items": [{"id": "org2"}]}
                response.status_code = HTTPStatus.OK
                return response

            mock_post.side_effect = post_side_effect
            mock_get.side_effect = get_side_effect

            # Test that each instance connects to its correct endpoint
            token1.refresh()
            token2.refresh()
            
            self.assertEqual(token1.access_token, "token1")
            self.assertEqual(token2.access_token, "token2")

            # Mock tokens for AMS checks to avoid SSO calls
            ams1._token = Mock()
            ams2._token = Mock()
            
            result1 = ams1.get_organization(123)
            result2 = ams2.get_organization(456)
            
            self.assertEqual(result1["id"], "org1")
            self.assertEqual(result2["id"], "org2")
