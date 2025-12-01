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
from django.db import models
from django.utils.functional import cached_property

from ansible_ai_connect.ai.api.aws.wca_secret_manager import Suffixes

logger = logging.getLogger(__name__)


def get_feature_flags():
    # Avoid circular dependency issue with lazy import
    from ansible_ai_connect.ai.feature_flags import FeatureFlags

    return FeatureFlags()


class ExternalOrganization(models.Model):
    id = models.IntegerField(primary_key=True)
    telemetry_opt_out = models.BooleanField(default=False, db_column="telemetry_opt_out")
    enable_anonymization = models.BooleanField(default=True)

    @property  # NOTE: The info dict is already cache in the seat_checker
    def name(self):
        seat_checker = apps.get_app_config("ai").get_seat_checker()
        organization_info = seat_checker.get_organization(self.id)
        return organization_info.get("name")

    @property
    def has_telemetry_opt_out(self):
        # For saas deployment mode, telemetry is opted-in by default (telemetry_opt_out=False)
        # For others, telemetry is not supported, considered opted-out (telemetry_opt_out=True)
        if settings.DEPLOYMENT_MODE == "saas":
            return self.telemetry_opt_out
        return True

    @cached_property
    def is_subscription_check_should_be_bypassed(self) -> bool:
        # Avoid circular dependency issue with lazy import
        from ansible_ai_connect.ai.feature_flags import WisdomFlags

        try:
            return self.__make_organization_request_to_launchdarkly(
                WisdomFlags.BYPASS_AAP_SUBSCRIPTION_CHECK
            )
        except Exception:
            # User should not be blocked if LaunchDarkly fails.
            return True

    @cached_property
    def has_api_key(self) -> bool:
        secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        org_has_api_key = secret_manager.secret_exists(self.id, Suffixes.API_KEY)
        return org_has_api_key

    def __make_organization_request_to_launchdarkly(self, flag: str) -> bool:
        if not settings.LAUNCHDARKLY_SDK_KEY:
            return False

        feature_flags = get_feature_flags()
        return feature_flags.check_flag(
            flag,
            {"kind": "organization", "key": str(self.id)},
        )
