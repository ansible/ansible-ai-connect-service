import logging
from enum import Enum

from django.conf import settings
from ldclient import Context
from users.models import User

logger = logging.getLogger(__name__)


class WisdomFlags(str, Enum):
    MODEL_NAME = "model_name"  # model name selection


class FeatureFlags:
    def __init__(self):
        if settings.LAUNCHDARKLY_SDK_KEY:
            import ldclient
            from ldclient.config import Config

            def create_ld_client():
                ldclient.set_config(Config(settings.LAUNCHDARKLY_SDK_KEY))
                client = ldclient.get()
                logger.info("feature flag client initialized")
                return client

            try:
                import uwsgidecorators
                uwsgidecorators.postfork(create_ld_client)
            except ImportError:
                pass

            self.client = create_ld_client()
        else:
            self.client = None

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
