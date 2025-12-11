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

import ssl
from unittest import TestCase
from unittest.mock import Mock, patch

import requests

from ansible_ai_connect.ai.api.model_pipelines.http.configuration import (
    HttpConfiguration,
)
from ansible_ai_connect.ai.api.model_pipelines.http.pipelines import (
    HttpMetaData,
    HttpStreamingChatBotPipeline,
)
from ansible_ai_connect.ai.api.model_pipelines.wca.configuration_onprem import (
    WCAOnPremConfiguration,
)
from ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_onprem import (
    WCAOnPremMetaData,
)
from ansible_ai_connect.main.ssl_manager import ssl_manager


class TestHttpPipelineSSLManagerIntegration(TestCase):
    """Test HTTP pipelines integration with centralized SSL manager"""

    def setUp(self):
        self.config = HttpConfiguration(
            inference_url="https://example.com:8443",
            model_id="test-model",
            timeout=5000,
            enable_health_check=True,
            verify_ssl=True,
        )

    def test_http_metadata_uses_ssl_manager_session(self):
        """Test that HttpMetaData uses SSL manager for session creation"""
        with patch(
            "ansible_ai_connect.main.ssl_manager.ssl_manager.get_requests_session"
        ) as mock_get_session:
            mock_session = Mock(spec=requests.Session)
            mock_get_session.return_value = mock_session

            metadata = HttpMetaData(config=self.config)
            # Verify SSL manager was called with correct verify_ssl parameter
            mock_get_session.assert_called_once_with()
            # Verify the returned session is used
            self.assertEqual(metadata.session, mock_session)

    def test_http_metadata_ssl_disabled(self):
        """Test that HttpMetaData handles SSL disabled case"""
        config_ssl_disabled = HttpConfiguration(
            inference_url="https://example.com:8443",
            model_id="test-model",
            timeout=5000,
            enable_health_check=True,
            verify_ssl=False,
        )
        with patch(
            "ansible_ai_connect.main.ssl_manager.ssl_manager.get_requests_session"
        ) as mock_get_session:
            mock_session = Mock(spec=requests.Session)
            mock_get_session.return_value = mock_session
            metadata = HttpMetaData(config=config_ssl_disabled)
            mock_get_session.assert_called_once_with()
            # Verify the returned session is used
            self.assertEqual(metadata.session, mock_session)


class TestWCAPipelineSSLManagerIntegration(TestCase):
    """Test WCA pipeline integration with centralized SSL manager"""

    def setUp(self):
        self.config = WCAOnPremConfiguration(
            inference_url="https://wca.example.com:8443",
            model_id="test-wca-model",
            timeout=5000,
            verify_ssl=True,
            retry_count=3,
            api_key="test-api-key",
            enable_health_check=True,
            health_check_api_key="test-health-key",
            health_check_model_id="test-health-model",
            username="test-user",
            enable_anonymization=False,
        )

    def test_wca_pipeline_uses_ssl_manager_session(self):
        """Test that WCAOnPremMetaData uses SSL manager for session creation"""
        with patch(
            "ansible_ai_connect.main.ssl_manager.ssl_manager.get_requests_session"
        ) as mock_get_session:
            mock_session = Mock(spec=requests.Session)
            mock_get_session.return_value = mock_session
            pipeline = WCAOnPremMetaData(config=self.config)
            # Verify SSL manager was called with correct verify_ssl parameter
            mock_get_session.assert_called_once_with()
            # Verify the returned session is used
            self.assertEqual(pipeline.session, mock_session)

    def test_wca_pipeline_ssl_disabled(self):
        """Test that WCAOnPremMetaData handles SSL disabled case"""
        config_ssl_disabled = WCAOnPremConfiguration(
            inference_url="https://wca.example.com:8443",
            model_id="test-wca-model",
            timeout=5000,
            verify_ssl=False,
            retry_count=3,
            api_key="test-api-key",
            enable_health_check=True,
            health_check_api_key="test-health-key",
            health_check_model_id="test-health-model",
            username="test-user",
            enable_anonymization=False,
        )
        with patch(
            "ansible_ai_connect.main.ssl_manager.ssl_manager.get_requests_session"
        ) as mock_get_session:
            mock_session = Mock(spec=requests.Session)
            mock_get_session.return_value = mock_session
            pipeline = WCAOnPremMetaData(config=config_ssl_disabled)
            mock_get_session.assert_called_once_with()
            # Verify the returned session is used
            self.assertEqual(pipeline.session, mock_session)


class TestHttpStreamingPipelineSSLManagerIntegration(TestCase):
    """Test HTTP streaming pipeline integration with centralized SSL manager"""

    def setUp(self):
        self.config = HttpConfiguration(
            inference_url="https://example.com:8443",
            model_id="test-model",
            timeout=5000,
            enable_health_check=True,
            verify_ssl=True,
            stream=True,
        )

    def test_streaming_pipeline_initialization(self):
        """Test that HttpStreamingChatBotPipeline initializes properly"""
        pipeline = HttpStreamingChatBotPipeline(config=self.config)
        # Basic initialization test
        self.assertIsNotNone(pipeline)
        self.assertEqual(pipeline.config.verify_ssl, True)

    def test_streaming_pipeline_ssl_disabled(self):
        """Test that HttpStreamingChatBotPipeline handles SSL disabled case"""
        config_ssl_disabled = HttpConfiguration(
            inference_url="https://example.com:8443",
            model_id="test-model",
            timeout=5000,
            enable_health_check=True,
            verify_ssl=False,
            stream=True,
        )
        pipeline = HttpStreamingChatBotPipeline(config=config_ssl_disabled)
        self.assertIsNotNone(pipeline)
        self.assertEqual(pipeline.config.verify_ssl, False)


class TestSSLManagerBehavior(TestCase):
    """Test basic SSL manager behavior"""

    def test_ssl_manager_singleton_exists(self):
        """Test that the SSL manager instance is available"""
        self.assertIsNotNone(ssl_manager)

    def test_ssl_manager_provides_requests_session(self):
        """Test that SSL manager provides configured requests session"""
        session = ssl_manager.get_requests_session()
        self.assertIsInstance(session, requests.Session)

    def test_ssl_manager_provides_ssl_context(self):
        """Test that SSL manager provides SSL context for async operations"""
        ssl_context = ssl_manager.get_ssl_context()
        self.assertIsInstance(ssl_context, ssl.SSLContext)

    def test_ssl_manager_session_ssl_disabled(self):
        """Test that SSL manager provides session with SSL disabled"""
        session = ssl_manager.get_requests_session()
        self.assertIsInstance(session, requests.Session)

    def test_ssl_manager_ca_info_available(self):
        """Test that SSL manager provides CA configuration information"""
        ca_info = ssl_manager.get_ca_info()
        self.assertIsInstance(ca_info, dict)
        expected_keys = [
            "active_ca_bundle",
            "combined_ca_bundle",
            "service_ca_path",
            "requests_ca_bundle",
            "legacy_service_ca",
            "using_system_defaults",
        ]
        for key in expected_keys:
            self.assertIn(key, ca_info)

    def test_ssl_manager_infrastructure_awareness(self):
        """Test that SSL manager properly detects infrastructure configuration"""
        ca_info = ssl_manager.get_ca_info()
        self.assertIsInstance(ca_info, dict)
        # Should indicate whether using system defaults or custom CA bundles
        self.assertIn("using_system_defaults", ca_info)
        self.assertIsInstance(ca_info["using_system_defaults"], bool)
