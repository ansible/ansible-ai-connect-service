import logging

from django.conf import settings
from ldclient import Context
from users.models import User

logger = logging.getLogger(__name__)


class FeatureFlags:
    import ldclient
    from ldclient.config import Config

    ldclient.set_config(Config(settings.FEATURE_FLAG_KEY))
    client = ldclient.get()
    logger.info("feature flag client initialized")

    def get(self, name: str, user: User, default: str):
        groups = list(user.groups.values_list("name", flat=True))
        userId = str(user.uuid)

        logger.debug(f"constructing user context for {userId}")
        user_context = (
            Context.builder(userId).set("username", user.username).set("groups", groups).build()
        )
        logger.debug(f"retrieving feature flag {name}")
        return self.client.variation(name, user_context, default)
