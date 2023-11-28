import logging
from enum import Enum

from django.conf import settings
from ldclient import Context
from ldclient.config import Config
from ldclient.client import LDClient
from users.models import User

logger = logging.getLogger(__name__)


class WisdomFlags(str, Enum):
    MODEL_NAME = "model_name"  # model name selection


class FeatureFlags:
    def __init__(self):
        self.client = None
        if settings.LAUNCHDARKLY_SDK_KEY:
            self.client = LDClient(
                Config(settings.LAUNCHDARKLY_SDK_KEY), start_wait=settings.LAUNCHDARKLY_SDK_TIMEOUT
            )
            logger.info("feature flag client initialized")

    def get(self, name: str, user: User, default: str):
        if self.client:
            if user.is_anonymous:
                user_context = Context.builder("AnonymousUser").anonymous(True).build()
            else:
                groups = list(user.groups.values_list("name", flat=True))
                userId = str(user.uuid)

                logger.debug(f"constructing user context for {userId}")
                user_context = (
                    Context.builder(userId)
                    .set("username", user.username)
                    .set("groups", groups)
                    .build()
                )
            logger.debug(f"retrieving feature flag {name}")
            return self.client.variation(name, user_context, default)
        else:
            raise Exception("feature flag client is not initialized")
