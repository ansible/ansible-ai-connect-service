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
        if not settings.LAUNCHDARKLY_SDK_KEY:
            return False

        # Avoid circular dependency issue with lazy import
        from ai.feature_flags import FeatureFlags

        feature_flags = FeatureFlags()
        return feature_flags.is_schema_2_telemetry_enabled(self.id)
