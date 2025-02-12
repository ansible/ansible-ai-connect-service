from ansible_base.resource_registry.registry import (
    ResourceConfig,
    ServiceAPIConfig,
    SharedResource,
)
from ansible_base.resource_registry.shared_types import UserType
from ansible_base.resource_registry.utils.resource_type_processor import (
    ResourceTypeProcessor,
)
from django.contrib.auth import get_user_model


class UserProcessor(ResourceTypeProcessor):
    def pre_serialize_additional(self):
        # These fields aren't supported in app, so we'll set them to blank
        setattr(self.instance, "external_auth_provider", None)
        setattr(self.instance, "external_auth_uid", None)
        setattr(self.instance, "organizations", [])
        setattr(self.instance, "organizations_administered", [])

        return self.instance


class APIConfig(ServiceAPIConfig):
    custom_resource_processors = {"shared.user": UserProcessor}
    service_type = "lightspeed"


RESOURCE_LIST = [
    ResourceConfig(
        get_user_model(),
        shared_resource=SharedResource(serializer=UserType, is_provider=False),
        name_field="username",
    ),
]
