import logging

from django.conf import settings
from django.db import models
from django.utils.functional import cached_property

logger = logging.getLogger(__name__)


class Organization(models.Model):
    id = models.IntegerField(primary_key=True)
    _telemetry_opt_out = models.BooleanField(default=False, db_column='telemetry_opt_out')

    @property
    def telemetry_opt_out(self):
        # For saas deployment mode, telemetry is opted-in by default (telemetry_opt_out=False)
        # For others, telemetry is not supported, considered opted-out (telemetry_opt_out=True)
        if settings.DEPLOYMENT_MODE == "saas":
            return self._telemetry_opt_out
        return True

    @telemetry_opt_out.setter
    def telemetry_opt_out(self, value):
        self._telemetry_opt_out = value

    @cached_property
    def is_subscription_check_should_be_bypassed(self) -> bool:
        # Avoid circular dependency issue with lazy import
        from ansible_wisdom.ai.feature_flags import WisdomFlags

        try:
            return self.__make_organization_request_to_launchdarkly(
                WisdomFlags.BYPASS_AAP_SUBSCRIPTION_CHECK
            )
        except Exception:
            # User should not be blocked if LaunchDarkly fails.
            return True

    def __make_organization_request_to_launchdarkly(self, flag: str) -> bool:
        if not settings.LAUNCHDARKLY_SDK_KEY:
            return False

        # Avoid circular dependency issue with lazy import
        from ansible_wisdom.ai.feature_flags import FeatureFlags

        feature_flags = FeatureFlags()
        return feature_flags.check_flag(
            flag,
            {'kind': 'organization', 'key': str(self.id)},
        )
