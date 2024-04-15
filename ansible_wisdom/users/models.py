import logging
import uuid

from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.functional import cached_property
from django_deprecate_fields import deprecate_field
from django_prometheus.models import ExportModelOperationsMixin

from ansible_wisdom.ai.api.aws.wca_secret_manager import Suffixes
from ansible_wisdom.organizations.models import Organization

from .constants import (
    FAUX_COMMERCIAL_USER_ORG_ID,
    USER_SOCIAL_AUTH_PROVIDER_AAP,
    USER_SOCIAL_AUTH_PROVIDER_OIDC,
)

logger = logging.getLogger("organizations")


class NonClashingForeignKey(models.ForeignKey):
    """
    models.ForeignKey(..) adds an "attfield" for the Foreign Key column.
    However, it simply appends "_id" to the "fieldname" leading to a conflict
    when trying to generate the database models. This works around the issue
    by using a different _template_ for the FK field.
    """

    def get_attname(self):
        return "fk_%s_id" % self.name


class User(ExportModelOperationsMixin('user'), AbstractUser):
    uuid = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    community_terms_accepted = models.DateTimeField(default=None, null=True)
    commercial_terms_accepted = models.DateTimeField(default=None, null=True)
    organization_id = deprecate_field(models.IntegerField(default=None, null=True))
    organization = NonClashingForeignKey(
        Organization,
        default=None,
        null=True,
        on_delete=models.CASCADE,
    )
    rh_user_is_org_admin = models.BooleanField(default=False)
    external_username = models.CharField(default="", null=False)

    @property
    def org_id(self):
        if self.groups.filter(name='Commercial').exists():
            return FAUX_COMMERCIAL_USER_ORG_ID
        if self.organization and self.organization.id:
            return self.organization.id
        return None

    def is_oidc_user(self) -> bool:
        if not self.social_auth.values():
            return False
        return self.social_auth.values()[0]["provider"] == USER_SOCIAL_AUTH_PROVIDER_OIDC

    def is_aap_user(self) -> bool:
        if not self.social_auth.values():
            return False
        return self.social_auth.values()[0]["provider"] == USER_SOCIAL_AUTH_PROVIDER_AAP

    @cached_property
    def rh_user_has_seat(self) -> bool:
        """True if the user comes from RHSSO and has a Wisdom Seat."""
        # For dev/test purposes only:
        if self.groups.filter(name='Commercial').exists():
            return True

        # user is of an on-prem AAP with valid license
        if self.is_aap_user():
            return self.rh_aap_licensed

        # Logic used during the transition and before the removal of the rh_user_has_seat attr
        if self.organization and self.rh_org_has_subscription:
            if not settings.ANSIBLE_AI_ENABLE_TECH_PREVIEW:
                return True

            secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
            org_has_api_key = secret_manager.secret_exists(self.organization.id, Suffixes.API_KEY)
            return org_has_api_key

        return False

    @cached_property
    def rh_org_has_subscription(self) -> bool:
        """True if the user
        1. is in unlimited group or
        2. is of an on-prem AAP with valid license or
        3. comes from RHSSO and the associated org has access to Wisdom
        """

        if self.organization and self.organization.is_subscription_check_should_be_bypassed:
            message = (
                "Bypass organization check for organization ID "
                f"{self.organization.id} and user UUID: {self.uuid}."
            )
            logger.info(message)
            return True

        if self.is_aap_user():
            return self.rh_aap_licensed

        if not self.is_oidc_user():
            return False

        seat_checker = apps.get_app_config("ai").get_seat_checker()
        if not seat_checker:
            return False
        rh_org_id = self.organization.id if self.organization else None
        return seat_checker.rh_org_has_subscription(rh_org_id)

    @cached_property
    def rh_aap_licensed(self) -> bool:
        return self.is_aap_user() and self.social_auth.values()[0]['extra_data']['aap_licensed']
