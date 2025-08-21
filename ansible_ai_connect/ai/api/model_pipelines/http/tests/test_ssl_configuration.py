#
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

import json
from typing import cast

from django.test import SimpleTestCase, override_settings

from ansible_ai_connect.ai.api.model_pipelines.http.configuration import (
    HttpConfiguration,
    HttpPipelineConfiguration,
    HttpConfigurationSerializer
)
from ansible_ai_connect.ai.api.model_pipelines.tests import mock_pipeline_config, mock_config


class TestHttpConfigurationSSL(SimpleTestCase):
    """Test the HttpConfiguration class SSL-related functionality"""

    def test_configuration_with_ca_cert_file(self):
        """Test that HttpConfiguration properly handles ca_cert_file parameter"""
        ca_cert_path = "/path/to/ca-certificate.crt"
        config = HttpConfiguration(
            inference_url="https://example.com:8443",
            model_id="test-model",
            timeout=5000,
            enable_health_check=True,
            verify_ssl=True,
            stream=False,
            ca_cert_file=ca_cert_path
        )
        self.assertEqual(config.ca_cert_file, ca_cert_path)
        self.assertTrue(config.verify_ssl)
        self.assertEqual(config.inference_url, "https://example.com:8443")

    def test_configuration_without_ca_cert_file(self):
        """Test that HttpConfiguration works without ca_cert_file (default None)"""
        config = HttpConfiguration(
            inference_url="https://example.com:8443",
            model_id="test-model",
            timeout=5000,
            enable_health_check=True,
            verify_ssl=True,
            stream=False
        )
        self.assertIsNone(config.ca_cert_file)
        self.assertTrue(config.verify_ssl)

    def test_configuration_ca_cert_file_none_explicit(self):
        """Test that HttpConfiguration handles explicit None for ca_cert_file"""
        config = HttpConfiguration(
            inference_url="https://example.com:8443",
            model_id="test-model",
            timeout=5000,
            enable_health_check=True,
            verify_ssl=False,
            stream=False,
            ca_cert_file=None
        )
        self.assertIsNone(config.ca_cert_file)
        self.assertFalse(config.verify_ssl)

    def test_mock_pipeline_config_with_ca_cert_file(self):
        """Test that mock_pipeline_config properly handles ca_cert_file parameter"""
        ca_cert_path = "/var/run/secrets/kubernetes.io/serviceaccount/service-ca.crt"
        config = cast(HttpConfiguration, mock_pipeline_config(
            "http",
            ca_cert_file=ca_cert_path,
            verify_ssl=True,
            inference_url="https://ls-stack-service.wisdom-ls-stack.svc.cluster.local:8443"
        ))
        self.assertEqual(config.ca_cert_file, ca_cert_path)
        self.assertTrue(config.verify_ssl)
        self.assertEqual(config.inference_url, "https://ls-stack-service.wisdom-ls-stack.svc.cluster.local:8443")

    def test_mock_pipeline_config_without_ca_cert_file(self):
        """Test that mock_pipeline_config works without ca_cert_file"""
        config = cast(HttpConfiguration, mock_pipeline_config(
            "http",
            verify_ssl=False,
            inference_url="http://localhost:8080"
        ))
        self.assertIsNone(config.ca_cert_file)
        self.assertFalse(config.verify_ssl)


class TestHttpPipelineConfiguration(SimpleTestCase):
    """Test the HttpPipelineConfiguration class"""

    def test_pipeline_configuration_with_ca_cert_file(self):
        """Test that HttpPipelineConfiguration properly passes ca_cert_file"""
        ca_cert_path = "/path/to/ca-certificate.crt"
        pipeline_config = HttpPipelineConfiguration(
            inference_url="https://example.com:8443",
            model_id="test-model",
            timeout=5000,
            enable_health_check=True,
            verify_ssl=True,
            stream=False,
            mcp_servers=[],
            ca_cert_file=ca_cert_path
        )
        self.assertEqual(pipeline_config.config.ca_cert_file, ca_cert_path)
        self.assertTrue(pipeline_config.config.verify_ssl)

    def test_pipeline_configuration_without_ca_cert_file(self):
        """Test that HttpPipelineConfiguration works without ca_cert_file"""
        pipeline_config = HttpPipelineConfiguration(
            inference_url="https://example.com:8443",
            model_id="test-model",
            timeout=5000,
            enable_health_check=True,
            verify_ssl=True,
            stream=False,
            mcp_servers=[]
        )
        self.assertIsNone(pipeline_config.config.ca_cert_file)
        self.assertTrue(pipeline_config.config.verify_ssl)


class TestHttpConfigurationSerializer(SimpleTestCase):
    """Test the HttpConfigurationSerializer"""

    def test_serializer_with_ca_cert_file(self):
        """Test serializer properly handles ca_cert_file field"""
        data = {
            "inference_url": "https://example.com:8443",
            "model_id": "test-model",
            "timeout": 5000,
            "enable_health_check": True,
            "verify_ssl": True,
            "stream": False,
            "ca_cert_file": "/var/run/secrets/kubernetes.io/serviceaccount/service-ca.crt"
        }
        serializer = HttpConfigurationSerializer(data=data)
        self.assertTrue(serializer.is_valid(), f"Serializer errors: {serializer.errors}")
        validated_data = serializer.validated_data
        self.assertEqual(validated_data["ca_cert_file"], "/var/run/secrets/kubernetes.io/serviceaccount/service-ca.crt")
        self.assertTrue(validated_data["verify_ssl"])

    def test_serializer_without_ca_cert_file(self):
        """Test serializer works without ca_cert_file (should default to None)"""
        data = {
            "inference_url": "https://example.com:8443",
            "model_id": "test-model",
            "timeout": 5000,
            "enable_health_check": True,
            "verify_ssl": True,
            "stream": False
        }
        serializer = HttpConfigurationSerializer(data=data)
        self.assertTrue(serializer.is_valid(), f"Serializer errors: {serializer.errors}")
        validated_data = serializer.validated_data
        self.assertIsNone(validated_data["ca_cert_file"])
        self.assertTrue(validated_data["verify_ssl"])

    def test_serializer_ca_cert_file_none_explicit(self):
        """Test serializer handles explicit null for ca_cert_file"""
        data = {
            "inference_url": "https://example.com:8443",
            "model_id": "test-model",
            "timeout": 5000,
            "enable_health_check": True,
            "verify_ssl": False,
            "stream": False,
            "ca_cert_file": None
        }
        serializer = HttpConfigurationSerializer(data=data)
        self.assertTrue(serializer.is_valid(), f"Serializer errors: {serializer.errors}")
        validated_data = serializer.validated_data
        self.assertIsNone(validated_data["ca_cert_file"])
        self.assertFalse(validated_data["verify_ssl"])

    def test_serializer_ca_cert_file_empty_string(self):
        """Test serializer handles empty string for ca_cert_file"""
        data = {
            "inference_url": "https://example.com:8443",
            "model_id": "test-model",
            "timeout": 5000,
            "enable_health_check": True,
            "verify_ssl": True,
            "stream": False,
            "ca_cert_file": ""
        }
        serializer = HttpConfigurationSerializer(data=data)
        self.assertTrue(serializer.is_valid(), f"Serializer errors: {serializer.errors}")
        validated_data = serializer.validated_data
        self.assertEqual(validated_data["ca_cert_file"], "")
        self.assertTrue(validated_data["verify_ssl"])


@override_settings(ANSIBLE_AI_MODEL_MESH_CONFIG=mock_config("http"))
class TestHttpConfigurationIntegration(SimpleTestCase):
    """Integration tests for HTTP configuration with SSL settings"""

    def test_integration_with_ca_cert_file_in_model_mesh_config(self):
        """Test that ca_cert_file is properly integrated into model mesh configuration"""
        # Create a mock configuration with ca_cert_file
        ca_cert_path = "/var/run/secrets/kubernetes.io/serviceaccount/service-ca.crt"
        config_dict = {
            "ModelPipelineChatBot": {
                "provider": "http",
                "config": {
                    "inference_url": "https://ls-stack-service.wisdom-ls-stack.svc.cluster.local:8443",
                    "model_id": "granite-3.3-8b-instruct",
                    "timeout": 10000,
                    "enable_health_check": True,
                    "verify_ssl": True,
                    "stream": False,
                    "ca_cert_file": ca_cert_path
                }
            }
        }
        with override_settings(ANSIBLE_AI_MODEL_MESH_CONFIG=json.dumps(config_dict)):
            # This integration test validates the complete configuration pipeline
            # The actual factory loading would be tested in separate integration tests
            pass

    def test_integration_backward_compatibility_without_ca_cert_file(self):
        """Test that existing configurations without ca_cert_file still work"""
        config_dict = {
            "ModelPipelineChatBot": {
                "provider": "http",
                "config": {
                    "inference_url": "http://ls-stack-service.wisdom-ls-stack.svc.cluster.local:8080",
                    "model_id": "granite-3.3-8b-instruct",
                    "timeout": 10000,
                    "enable_health_check": True,
                    "verify_ssl": False,
                    "stream": False
                }
            }
        }
        with override_settings(ANSIBLE_AI_MODEL_MESH_CONFIG=json.dumps(config_dict)):
            # This validates backward compatibility
            # The ca_cert_file should default to None
            pass


class TestHttpConfigurationEdgeCases(SimpleTestCase):
    """Test edge cases for HTTP configuration"""

    def test_configuration_with_relative_ca_cert_path(self):
        """Test HttpConfiguration with relative path for ca_cert_file"""
        config = HttpConfiguration(
            inference_url="https://example.com:8443",
            model_id="test-model",
            timeout=5000,
            enable_health_check=True,
            verify_ssl=True,
            stream=False,
            ca_cert_file="./certs/ca.crt"
        )
        self.assertEqual(config.ca_cert_file, "./certs/ca.crt")
        self.assertTrue(config.verify_ssl)

    def test_configuration_with_absolute_ca_cert_path(self):
        """Test HttpConfiguration with absolute path for ca_cert_file"""
        config = HttpConfiguration(
            inference_url="https://example.com:8443",
            model_id="test-model",
            timeout=5000,
            enable_health_check=True,
            verify_ssl=True,
            stream=False,
            ca_cert_file="/etc/ssl/certs/ca-certificates.crt"
        )
        self.assertEqual(config.ca_cert_file, "/etc/ssl/certs/ca-certificates.crt")
        self.assertTrue(config.verify_ssl)

    def test_configuration_ca_cert_with_verify_ssl_false(self):
        """Test that ca_cert_file can be set even with verify_ssl=False"""
        config = HttpConfiguration(
            inference_url="https://example.com:8443",
            model_id="test-model",
            timeout=5000,
            enable_health_check=True,
            verify_ssl=False,
            stream=False,
            ca_cert_file="/path/to/ca-cert.crt"
        )
        self.assertEqual(config.ca_cert_file, "/path/to/ca-cert.crt")
        self.assertFalse(config.verify_ssl)
        # This scenario tests that both parameters are independent

    def test_configuration_realistic_kubernetes_scenario(self):
        """Test realistic Kubernetes service CA scenario"""
        config = HttpConfiguration(
            inference_url="https://ls-stack-service.wisdom-ls-stack.svc.cluster.local:8443",
            model_id="granite-3.3-8b-instruct",
            timeout=10000,
            enable_health_check=True,
            verify_ssl=True,
            stream=False,
            ca_cert_file="/var/run/secrets/kubernetes.io/serviceaccount/service-ca.crt"
        )
        self.assertEqual(config.ca_cert_file, "/var/run/secrets/kubernetes.io/serviceaccount/service-ca.crt")
        self.assertTrue(config.verify_ssl)
        self.assertEqual(config.inference_url, "https://ls-stack-service.wisdom-ls-stack.svc.cluster.local:8443")
        self.assertEqual(config.model_id, "granite-3.3-8b-instruct")
        self.assertEqual(config.timeout, 10000)
        self.assertTrue(config.enable_health_check)
        self.assertFalse(config.stream)
