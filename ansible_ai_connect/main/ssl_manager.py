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
from django.conf import settings

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

        # Legacy settings support for backward compatibility
        self._service_ca_path = getattr(settings, "SERVICE_CA_PATH", None)

        logger.info("SSL Manager: Infrastructure mode initialized")
        logger.debug("SSL Manager: Combined CA bundle: %s", self.combined_ca_bundle)
        logger.debug("SSL Manager: Service CA: %s", self.service_ca_path)
        logger.debug("SSL Manager: Requests CA bundle: %s", self.requests_ca_bundle)
        logger.debug("SSL Manager: Legacy service CA: %s", self._service_ca_path)

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
        # Priority 1: Infrastructure-provided combined bundle (best)
        if self.combined_ca_bundle and os.path.exists(self.combined_ca_bundle):
            logger.debug(
                "SSL Manager: Using infrastructure combined CA bundle: %s", self.combined_ca_bundle
            )
            return self.combined_ca_bundle

        # Priority 2: Environment REQUESTS_CA_BUNDLE
        if self.requests_ca_bundle and os.path.exists(self.requests_ca_bundle):
            logger.debug("SSL Manager: Using REQUESTS_CA_BUNDLE: %s", self.requests_ca_bundle)
            return self.requests_ca_bundle

        # Priority 3: Service CA (for internal services)
        if self.service_ca_path and os.path.exists(self.service_ca_path):
            logger.debug("SSL Manager: Using service CA: %s", self.service_ca_path)
            return self.service_ca_path

        # Priority 4: Legacy settings service CA
        if self._service_ca_path and os.path.exists(self._service_ca_path):
            logger.debug("SSL Manager: Using legacy service CA: %s", self._service_ca_path)
            return self._service_ca_path

        # No custom CA bundle found - use system defaults
        logger.debug("SSL Manager: No custom CA bundle found, using system defaults")
        return None

    def get_requests_session(self, verify_ssl: bool = True) -> requests.Session:
        """Get requests session with infrastructure-managed SSL configuration.
        Args:
            verify_ssl: Whether SSL verification should be enabled
        Returns:
            Configured requests session with proper SSL settings.
            Falls back to system defaults if custom CA bundles are not accessible.
        """
        session = requests.Session()

        if verify_ssl:
            try:
                ca_bundle_path = self._get_ca_bundle_path()
                if ca_bundle_path:
                    # Verify the CA bundle file is readable before using it
                    if os.path.exists(ca_bundle_path) and os.access(ca_bundle_path, os.R_OK):
                        session.verify = ca_bundle_path
                        logger.debug(
                            "SSL Manager: Session configured with CA bundle: %s", ca_bundle_path
                        )
                    else:
                        logger.warning(
                            "SSL Manager: CA bundle not accessible: %s,"
                            + " falling back to system defaults",
                            ca_bundle_path,
                        )
                        # session.verify defaults to True, which uses system CAs
                else:
                    logger.debug("SSL Manager: Session using system default CA verification")
                    # session.verify defaults to True, which uses system CAs

            except (OSError, AttributeError) as e:
                logger.warning(
                    "SSL Manager: SSL configuration issue (non-fatal): %s, using system defaults", e
                )
                # Don't raise exception, just fall back to system defaults
                # session.verify defaults to True
        else:
            session.verify = False
            logger.debug("SSL Manager: SSL verification disabled")

        return session

    def get_ssl_context(self, verify_ssl: bool = True) -> Optional[ssl.SSLContext]:
        """Get SSL context for aiohttp with infrastructure-managed certificates.
        Args:
            verify_ssl: Whether SSL verification should be enabled
        Returns:
            SSLContext configured with CA bundle, or None if verification disabled
        Raises:
            ssl.SSLError: If SSL context creation fails
        """
        if not verify_ssl:
            return None

        try:
            ca_bundle_path = self._get_ca_bundle_path()
            if ca_bundle_path:
                context = ssl.create_default_context(cafile=ca_bundle_path)
                logger.debug("SSL Manager: Created SSL context with CA bundle: %s", ca_bundle_path)
                return context
            else:
                # Use system default CA bundle
                context = ssl.create_default_context()
                logger.debug("SSL Manager: Created SSL context with system defaults")
                return context

        except ssl.SSLError as e:
            logger.error("SSL Manager: Failed to create SSL context: %s", e)
            raise

    def get_ca_info(self) -> dict:
        """Get information about the current CA configuration.
        Returns:
            Dictionary with CA configuration details for debugging
        """
        ca_bundle_path = self._get_ca_bundle_path()
        return {
            "active_ca_bundle": ca_bundle_path,
            "combined_ca_bundle": self.combined_ca_bundle,
            "service_ca_path": self.service_ca_path,
            "requests_ca_bundle": self.requests_ca_bundle,
            "legacy_service_ca": self._service_ca_path,
            "ca_bundle_exists": (
                ca_bundle_path and os.path.exists(ca_bundle_path) if ca_bundle_path else None
            ),
            "using_system_defaults": ca_bundle_path is None,
        }


# Global instance
ssl_manager = SSLManager()
