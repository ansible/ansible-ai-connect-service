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

# from unittest.mock import patch

# from django.test import RequestFactory, override_settings

# from ansible_ai_connect.ai.api.model_pipelines.tests import mock_config
# from ansible_ai_connect.main.utils import (
#     get_project_name_with_wca_suffix,
#     has_wca_providers,
# )
# from ansible_ai_connect.test_utils import WisdomServiceLogAwareTestCase

from unittest.mock import patch

from django.test import RequestFactory

from ansible_ai_connect.ai.api.model_pipelines.factory import ModelPipelineFactory
from ansible_ai_connect.ai.api.model_pipelines.tests import mock_config
from ansible_ai_connect.main.utils import (
    get_project_name_with_wca_suffix,
    has_wca_providers,
)
from ansible_ai_connect.test_utils import WisdomServiceLogAwareTestCase


class TestHasWCAProvidersWithWCAProvider(WisdomServiceLogAwareTestCase):
    def test_returns_true_with_wca_provider(self):
        """Test that has_wca_providers returns True when WCA provider is configured."""
        # Create a factory with WCA config directly, without affecting global state
        config_path = (
            "ansible_ai_connect.ai.api.model_pipelines.config_loader.settings."
            "ANSIBLE_AI_MODEL_MESH_CONFIG"
        )
        with patch(config_path, mock_config("wca")):
            factory = ModelPipelineFactory()
            with patch("ansible_ai_connect.main.utils.apps.get_app_config") as mock_app:
                mock_app.return_value._pipeline_factory = factory
                self.assertTrue(has_wca_providers())


class TestHasWCAProvidersWithWCAOnPremProvider(WisdomServiceLogAwareTestCase):
    def test_returns_true_with_wca_onprem_provider(self):
        """Test that has_wca_providers returns True when WCA-onprem provider is configured."""
        config_path = (
            "ansible_ai_connect.ai.api.model_pipelines.config_loader.settings."
            "ANSIBLE_AI_MODEL_MESH_CONFIG"
        )
        with patch(config_path, mock_config("wca-onprem")):
            factory = ModelPipelineFactory()
            with patch("ansible_ai_connect.main.utils.apps.get_app_config") as mock_app:
                mock_app.return_value._pipeline_factory = factory
                self.assertTrue(has_wca_providers())


class TestHasWCAProvidersWithHttpProvider(WisdomServiceLogAwareTestCase):
    def test_returns_false_with_http_provider(self):
        """Test that has_wca_providers returns False when HTTP provider is configured."""
        config_path = (
            "ansible_ai_connect.ai.api.model_pipelines.config_loader.settings."
            "ANSIBLE_AI_MODEL_MESH_CONFIG"
        )
        with patch(config_path, mock_config("http")):
            factory = ModelPipelineFactory()
            with patch("ansible_ai_connect.main.utils.apps.get_app_config") as mock_app:
                mock_app.return_value._pipeline_factory = factory
                self.assertFalse(has_wca_providers())


class TestHasWCAProvidersWithEmptyConfig(WisdomServiceLogAwareTestCase):
    def test_returns_false_with_empty_config(self):
        """Test that has_wca_providers returns False with empty configuration."""
        config_path = (
            "ansible_ai_connect.ai.api.model_pipelines.config_loader.settings."
            "ANSIBLE_AI_MODEL_MESH_CONFIG"
        )
        with patch(config_path, "{}"):
            factory = ModelPipelineFactory()
            with patch("ansible_ai_connect.main.utils.apps.get_app_config") as mock_app:
                mock_app.return_value._pipeline_factory = factory
                self.assertFalse(has_wca_providers())


class TestGetProjectNameWithWCASuffixWithRealWCAConfig(WisdomServiceLogAwareTestCase):
    def test_integration_with_real_wca_config(self):
        """Integration test using real configuration."""
        config_path = (
            "ansible_ai_connect.ai.api.model_pipelines.config_loader.settings."
            "ANSIBLE_AI_MODEL_MESH_CONFIG"
        )
        with patch(config_path, mock_config("wca")):
            factory = ModelPipelineFactory()
            with patch("ansible_ai_connect.main.utils.apps.get_app_config") as mock_app:
                mock_app.return_value._pipeline_factory = factory
                result = get_project_name_with_wca_suffix("Ansible Lightspeed")
                self.assertEqual(result, "Ansible Lightspeed with IBM watsonx Code Assistant")


class TestGetProjectNameWithWCASuffixWithRealNonWCAConfig(WisdomServiceLogAwareTestCase):
    def test_integration_with_real_non_wca_config(self):
        """Integration test using real non-WCA configuration."""
        config_path = (
            "ansible_ai_connect.ai.api.model_pipelines.config_loader.settings."
            "ANSIBLE_AI_MODEL_MESH_CONFIG"
        )
        with patch(config_path, mock_config("dummy")):
            factory = ModelPipelineFactory()
            with patch("ansible_ai_connect.main.utils.apps.get_app_config") as mock_app:
                mock_app.return_value._pipeline_factory = factory
                result = get_project_name_with_wca_suffix("Ansible Lightspeed")
                self.assertEqual(result, "Ansible Lightspeed")


class TestGetProjectNameWithWCASuffix(WisdomServiceLogAwareTestCase):
    def test_adds_suffix_when_wca_providers_exist(self):
        """Test that suffix is added when WCA providers are detected."""
        with patch("ansible_ai_connect.main.utils.has_wca_providers", return_value=True):
            result = get_project_name_with_wca_suffix("Ansible Lightspeed")
            self.assertEqual(result, "Ansible Lightspeed with IBM watsonx Code Assistant")

    def test_no_suffix_when_no_wca_providers(self):
        """Test that no suffix is added when no WCA providers are detected."""
        with patch("ansible_ai_connect.main.utils.has_wca_providers", return_value=False):
            result = get_project_name_with_wca_suffix("Ansible Lightspeed")
            self.assertEqual(result, "Ansible Lightspeed")

    def test_handles_empty_base_name(self):
        """Test that function handles empty base project name."""
        with patch("ansible_ai_connect.main.utils.has_wca_providers", return_value=True):
            result = get_project_name_with_wca_suffix("")
            self.assertEqual(result, " with IBM watsonx Code Assistant")

    def test_handles_none_base_name(self):
        """Test that function handles None as base project name."""
        with patch("ansible_ai_connect.main.utils.has_wca_providers", return_value=True):
            result = get_project_name_with_wca_suffix(None)
            self.assertEqual(result, "None with IBM watsonx Code Assistant")

    def test_preserves_base_name_when_no_wca(self):
        """Test that base name is preserved exactly when no WCA providers."""
        test_names = [
            "Ansible AI Connect",
            "Custom Project Name",
            "Project with Special Characters !@#",
            "   Padded Name   ",
        ]

        with patch("ansible_ai_connect.main.utils.has_wca_providers", return_value=False):
            for base_name in test_names:
                with self.subTest(base_name=base_name):
                    result = get_project_name_with_wca_suffix(base_name)
                    self.assertEqual(result, base_name)

    def test_idempotent_with_existing_suffix_and_wca_providers(self):
        """Test function is idempotent when suffix exists and WCA providers present."""
        base_name = "Ansible Lightspeed with IBM watsonx Code Assistant"
        with patch("ansible_ai_connect.main.utils.has_wca_providers", return_value=True):
            result = get_project_name_with_wca_suffix(base_name)
            self.assertEqual(result, "Ansible Lightspeed with IBM watsonx Code Assistant")

    def test_idempotent_with_existing_suffix_and_no_wca_providers(self):
        """Test that function preserves existing suffix even when no WCA providers."""
        base_name = "Ansible Lightspeed with IBM watsonx Code Assistant"
        with patch("ansible_ai_connect.main.utils.has_wca_providers", return_value=False):
            result = get_project_name_with_wca_suffix(base_name)
            self.assertEqual(result, "Ansible Lightspeed with IBM watsonx Code Assistant")

    def test_handles_partial_suffix_match(self):
        """Test that function doesn't get confused by partial suffix matches."""
        test_cases = [
            "Ansible with IBM",
            "Project with IBM watsonx",
            "Ansible IBM watsonx Code Assistant",
            "with IBM watsonx Code Assistant prefix",
        ]

        with patch("ansible_ai_connect.main.utils.has_wca_providers", return_value=True):
            for base_name in test_cases:
                with self.subTest(base_name=base_name):
                    result = get_project_name_with_wca_suffix(base_name)
                    expected = f"{base_name} with IBM watsonx Code Assistant"
                    self.assertEqual(result, expected)

    def test_case_sensitive_suffix_matching(self):
        """Test that suffix matching is case sensitive."""
        test_cases = [
            "Ansible Lightspeed with ibm watsonx code assistant",  # lowercase
            "Ansible Lightspeed with IBM WATSONX CODE ASSISTANT",  # uppercase
            "Ansible Lightspeed With IBM Watsonx Code Assistant",  # mixed case
        ]

        with patch("ansible_ai_connect.main.utils.has_wca_providers", return_value=True):
            for base_name in test_cases:
                with self.subTest(base_name=base_name):
                    result = get_project_name_with_wca_suffix(base_name)
                    expected = f"{base_name} with IBM watsonx Code Assistant"
                    self.assertEqual(result, expected)

    def test_multiple_calls_are_idempotent(self):
        """Test that calling the function multiple times produces the same result."""
        base_name = "Ansible Lightspeed"

        with patch("ansible_ai_connect.main.utils.has_wca_providers", return_value=True):
            # First call
            result1 = get_project_name_with_wca_suffix(base_name)
            # Second call with result of first call
            result2 = get_project_name_with_wca_suffix(result1)
            # Third call with result of second call
            result3 = get_project_name_with_wca_suffix(result2)

            expected = "Ansible Lightspeed with IBM watsonx Code Assistant"
            self.assertEqual(result1, expected)
            self.assertEqual(result2, expected)
            self.assertEqual(result3, expected)

    def test_empty_string_with_existing_suffix_check(self):
        """Test behavior with empty string (edge case for endswith check)."""
        with patch("ansible_ai_connect.main.utils.has_wca_providers", return_value=True):
            result = get_project_name_with_wca_suffix("")
            self.assertEqual(result, " with IBM watsonx Code Assistant")

    def test_none_value_with_existing_suffix_check(self):
        """Test behavior with None value (edge case for endswith check)."""
        with patch("ansible_ai_connect.main.utils.has_wca_providers", return_value=True):
            result = get_project_name_with_wca_suffix(None)
            self.assertEqual(result, "None with IBM watsonx Code Assistant")

    def test_no_suffix_for_chatbot_route_with_wca_providers(self):
        """Test that no suffix is added when next param starts with /chatbot."""
        request = RequestFactory().get("/login?next=/chatbot")
        with patch("ansible_ai_connect.main.utils.has_wca_providers", return_value=True):
            result = get_project_name_with_wca_suffix("Ansible Lightspeed", request)
            self.assertEqual(result, "Ansible Lightspeed")

    def test_no_suffix_for_chatbot_route_with_path(self):
        """Test that no suffix is added when next param is /chatbot/something."""
        request = RequestFactory().get("/login?next=/chatbot/")
        with patch("ansible_ai_connect.main.utils.has_wca_providers", return_value=True):
            result = get_project_name_with_wca_suffix("Ansible Lightspeed", request)
            self.assertEqual(result, "Ansible Lightspeed")

    def test_suffix_added_for_non_chatbot_routes(self):
        """Test that suffix is added for non-chatbot routes when WCA providers exist."""
        request = RequestFactory().get("/login?next=/home")
        with patch("ansible_ai_connect.main.utils.has_wca_providers", return_value=True):
            result = get_project_name_with_wca_suffix("Ansible Lightspeed", request)
            self.assertEqual(result, "Ansible Lightspeed with IBM watsonx Code Assistant")

    def test_suffix_added_for_empty_next_param(self):
        """Test that suffix is added when next param is empty."""
        request = RequestFactory().get("/login?next=")
        with patch("ansible_ai_connect.main.utils.has_wca_providers", return_value=True):
            result = get_project_name_with_wca_suffix("Ansible Lightspeed", request)
            self.assertEqual(result, "Ansible Lightspeed with IBM watsonx Code Assistant")

    def test_suffix_added_when_no_next_param(self):
        """Test that suffix is added when there is no next param."""
        request = RequestFactory().get("/login")
        with patch("ansible_ai_connect.main.utils.has_wca_providers", return_value=True):
            result = get_project_name_with_wca_suffix("Ansible Lightspeed", request)
            self.assertEqual(result, "Ansible Lightspeed with IBM watsonx Code Assistant")

    def test_backward_compatibility_without_request(self):
        """Test that function works without request parameter for backward compatibility."""
        with patch("ansible_ai_connect.main.utils.has_wca_providers", return_value=True):
            result = get_project_name_with_wca_suffix("Ansible Lightspeed")
            self.assertEqual(result, "Ansible Lightspeed with IBM watsonx Code Assistant")

    def test_chatbot_route_case_sensitivity(self):
        """Test that chatbot route detection is case sensitive."""
        request = RequestFactory().get("/login?next=/CHATBOT")
        with patch("ansible_ai_connect.main.utils.has_wca_providers", return_value=True):
            result = get_project_name_with_wca_suffix("Ansible Lightspeed", request)
            # Should add suffix because /CHATBOT != /chatbot
            self.assertEqual(result, "Ansible Lightspeed with IBM watsonx Code Assistant")
