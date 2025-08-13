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

import logging

from django.apps import apps
from django.conf import settings

logger = logging.getLogger(__name__)


def has_wca_providers() -> bool:
    """Check if any ModelPipeline is configured to use WCA or WCA-onprem providers."""
    try:
        ai_app = apps.get_app_config("ai")
        factory = ai_app._pipeline_factory
        if not factory or not factory.pipelines_config:
            return False

        # Check all pipeline configurations for WCA providers
        for pipeline_name, pipeline_config in factory.pipelines_config.items():
            if hasattr(pipeline_config, "provider") and pipeline_config.provider in [
                "wca",
                "wca-onprem",
            ]:
                return True
        return False
    except Exception:
        # If there's any error accessing the configuration, default to False
        logger.exception("Error checking for WCA providers")
        return False


def get_project_name_with_wca_suffix(base_project_name: str, request=None) -> str:
    """Get project name with WCA suffix if WCA providers are configured.

    Args:
        base_project_name: The base project name
        request: Django request object (optional) - used to check for chatbot routes

    Returns:
        Project name with or without WCA suffix based on configuration and route
    """
    wca_suffix = settings.ANSIBLE_AI_PROJECT_WCA_SUFFIX

    # If the name already ends with the suffix, return as-is
    if base_project_name and base_project_name.endswith(wca_suffix):
        return base_project_name

    # Check if this is a chatbot route redirect - don't add suffix for chatbot routes
    if request and request.GET.get("next", "").startswith("/chatbot"):
        return base_project_name

    # Add suffix only if WCA providers are configured
    if has_wca_providers():
        return f"{base_project_name}{wca_suffix}"

    return base_project_name
