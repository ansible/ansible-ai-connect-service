import logging

from django.conf import settings
from django.db import models
from django.utils.functional import cached_property

logger = logging.getLogger(__name__)


class Organization(models.Model):
    id = models.IntegerField(primary_key=True)
    telemetry_opt_out = models.BooleanField(default=False)

    @cached_property
    def is_schema_2_telemetry_enabled(self) -> bool:
        # Avoid circular dependency issue with lazy import
        from ansible_wisdom.ai.feature_flags import WisdomFlags

        return self.__make_organization_request_to_launchdarkly(
            WisdomFlags.SCHEMA_2_TELEMETRY_ORG_ENABLED
        )

    @cached_property
    def is_unlimited_access_allowed(self) -> bool:
        # Avoid circular dependency issue with lazy import
        from ansible_wisdom.ai.feature_flags import WisdomFlags

        return self.__make_organization_request_to_launchdarkly(WisdomFlags.SPECIAL_WCA_ACCESS_ORGS)

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
