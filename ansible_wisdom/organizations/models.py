import logging

from django.conf import settings
from django.db import models
from django.utils.functional import cached_property

logger = logging.getLogger(__name__)


class Organization(models.Model):
    id = models.IntegerField(primary_key=True)
    telemetry_opt_out = models.BooleanField(default=False)

    @cached_property
    def is_schema_2_telemetry_override_enabled(self):
        if not settings.LAUNCHDARKLY_SDK_KEY:
            return False

        # Avoid circular dependency issue with lazy import
        from ai.feature_flags import FeatureFlags, WisdomFlags

        feature_flags = FeatureFlags()
        org_ids: str = feature_flags.get(WisdomFlags.SCHEMA_2_TELEMETRY_ORG_ID_WHITE_LIST, None, '')
        if len(org_ids) == 0:
            return False

        # Favor cast to str vs cast to int as we cannot
        # guarantee Users defined numbers in LaunchDarkly
        return any(org_id == str(self.id) for org_id in org_ids.split(','))
