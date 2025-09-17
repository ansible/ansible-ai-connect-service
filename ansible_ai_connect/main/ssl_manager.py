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
import os
import ssl
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class SSLManager:
    """Infrastructure-aware SSL manager that leverages Kubernetes/OpenShift SSL configuration.
    This manager delegates SSL configuration to the infrastructure layer, using
    environment variables and mounted CA bundles provided by the operator.
    This approach eliminates application-level SSL complexity and follows
    cloud-native best practices.
    Features:
    - Infrastructure-first approach using operator-provided CA bundles
    - No temporary file management
    - Environment variable driven configuration
    """

    def __init__(self):
        # Infrastructure-provided CA bundle paths (from operator)
        self.combined_ca_bundle = os.environ.get("COMBINED_CA_BUNDLE_PATH")
        self.service_ca_path = os.environ.get("SERVICE_CA_PATH")
        self.requests_ca_bundle = os.environ.get("REQUESTS_CA_BUNDLE")

        logger.info("SSL Manager: Infrastructure mode initialized")
        logger.debug("SSL Manager: Combined CA bundle: %s", self.combined_ca_bundle)
        logger.debug("SSL Manager: Service CA: %s", self.service_ca_path)
        logger.debug("SSL Manager: Requests CA bundle: %s", self.requests_ca_bundle)

    def _get_legacy_service_ca_path(self) -> Optional[str]:
        """Get legacy service CA path from Django settings with lazy loading.
        This is to ensure SSL manager can be imported safely in any context.
        """
        try:
            from django.conf import settings

            return getattr(settings, "SERVICE_CA_PATH", None)
        except (ImportError, AttributeError, Exception):
            # Django not configured, settings not available, or ImproperlyConfigured
            return None

    def _get_ca_bundle_path(self) -> Optional[str]:
        """Get the best available CA bundle path with prioritized fallback.
        Priority order:
        1. Infrastructure-provided combined bundle (operator creates this)
        2. REQUESTS_CA_BUNDLE environment variable
        3. Service CA from environment
        4. Legacy service CA from settings
        5. None (use system defaults)
        Returns:
            Path to CA bundle file or None for system defaults
        """
        # Infrastructure-provided combined bundle
        if self.combined_ca_bundle and os.path.exists(self.combined_ca_bundle):
            logger.debug(
                "SSL Manager: Using infrastructure combined CA bundle: %s", self.combined_ca_bundle
            )
            return self.combined_ca_bundle

        # Environment REQUESTS_CA_BUNDLE
        if self.requests_ca_bundle and os.path.exists(self.requests_ca_bundle):
            logger.debug("SSL Manager: Using REQUESTS_CA_BUNDLE: %s", self.requests_ca_bundle)
            return self.requests_ca_bundle

        # Service CA (for internal services)
        if self.service_ca_path and os.path.exists(self.service_ca_path):
            logger.debug("SSL Manager: Using service CA: %s", self.service_ca_path)
            return self.service_ca_path

        # Legacy settings service CA (lazy loaded)
        legacy_service_ca = self._get_legacy_service_ca_path()
        if legacy_service_ca and os.path.exists(legacy_service_ca):
            logger.debug("SSL Manager: Using legacy service CA: %s", legacy_service_ca)
            return legacy_service_ca

        # No custom CA bundle found - use system defaults
        logger.debug("SSL Manager: No custom CA bundle found, using system defaults")
        return None

    def get_requests_session(self) -> requests.Session:
        """Get requests session with infrastructure-managed SSL configuration.
        Args:
            verify_ssl: Whether SSL verification should be enabled
        Returns:
            Configured requests session with proper SSL settings.
        Raises:
            OSError: If SSL configuration fails
        """
        session = requests.Session()
        # SSL verification enabled - configure with custom or system CA bundle
        try:
            ca_bundle_path = self._get_ca_bundle_path()
            if ca_bundle_path:
                session.verify = ca_bundle_path
                logger.debug("SSL Manager: Session configured with CA bundle: %s", ca_bundle_path)
        except (OSError, AttributeError) as e:
            # SSL configuration errors should be fatal
            error_msg = f"SSL Manager: Fatal SSL configuration error: {e}"
            logger.exception(error_msg)
            raise OSError(error_msg) from e

        return session

    def get_ssl_context(self) -> ssl.SSLContext:
        """Get SSL context for aiohttp with infrastructure-managed certificates.
        Args:
            verify_ssl: Whether SSL verification should be enabled
        Returns:
            SSLContext configured with CA bundle, or None if verification disabled
        Raises:
            ssl.SSLError: If SSL context creation fails
            OSError: If SSL configuration fails
        """
        # SSL verification enabled - create context with custom or system CA bundle
        try:
            ca_bundle_path = self._get_ca_bundle_path()
            if ca_bundle_path:
                context = ssl.create_default_context(cafile=ca_bundle_path)
                if context is not None:
                    logger.debug(
                        "SSL Manager: Created SSL context with CA bundle: %s", ca_bundle_path
                    )
                    return context
                raise ssl.SSLError("SSL context creation returned None unexpectedly")
            else:
                # Use system default CA bundle
                context = ssl.create_default_context()
                if context is not None:
                    logger.debug("SSL Manager: Created SSL context with system defaults")
                    return context
                raise ssl.SSLError("SSL context creation returned None unexpectedly")
        except ssl.SSLError as e:
            logger.exception("SSL Manager: Failed to create SSL context: %s", e)
            raise
        except (OSError, AttributeError) as e:
            # SSL configuration errors should be fatal
            error_msg = f"SSL Manager: Fatal SSL configuration error for context: {e}"
            logger.exception(error_msg)
            raise OSError(error_msg) from e

    def get_ca_info(self) -> dict:
        """Get information about the current CA configuration.
        Returns:
            Dictionary with CA configuration details for debugging
        """
        ca_bundle_path = self._get_ca_bundle_path()
        legacy_service_ca = self._get_legacy_service_ca_path()
        return {
            "active_ca_bundle": ca_bundle_path,
            "combined_ca_bundle": self.combined_ca_bundle,
            "service_ca_path": self.service_ca_path,
            "requests_ca_bundle": self.requests_ca_bundle,
            "legacy_service_ca": legacy_service_ca,
            "ca_bundle_exists": (
                ca_bundle_path and os.path.exists(ca_bundle_path) if ca_bundle_path else None
            ),
            "using_system_defaults": ca_bundle_path is None,
        }


# Global instance
ssl_manager = SSLManager()
