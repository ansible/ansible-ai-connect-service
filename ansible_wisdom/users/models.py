import logging
import uuid

from django.apps import apps
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.functional import cached_property
from django_deprecate_fields import deprecate_field
from django_prometheus.models import ExportModelOperationsMixin
from organizations.models import Organization

from .constants import FAUX_COMMERCIAL_USER_ORG_ID, USER_SOCIAL_AUTH_PROVIDER_OIDC

logger = logging.getLogger(__name__)


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
        if self.social_auth.values()[0]["provider"] != USER_SOCIAL_AUTH_PROVIDER_OIDC:
            return False

        return True

    # It should be static since we in tests we have AnonymUser and for this case
    # we just use static User.is_opt_out method.
    @staticmethod
    def is_opt_out(user):
        return (
            True
            if hasattr(user, 'organization')
            and user.organization is not None
            and user.organization.telemetry_opt_out
            else False
        )

    @cached_property
    def rh_user_has_seat(self) -> bool:
        """True if the user comes from RHSSO and has a Wisdom Seat."""
        # For dev/test purposes only:
        if self.groups.filter(name='Commercial').exists():
            return True

        if not self.is_oidc_user():
            return False

        seat_checker = apps.get_app_config("ai").get_seat_checker()
        if not seat_checker:
            return False
        uid = self.social_auth.values()[0]["uid"]
        rh_org_id = self.organization.id if self.organization else None
        return seat_checker.check(uid, self.external_username, rh_org_id)

    @cached_property
    def rh_org_has_subscription(self) -> bool:
        """True if the user comes from RHSSO and the associated org has access to Wisdom."""
        if not self.is_oidc_user():
            return False

        seat_checker = apps.get_app_config("ai").get_seat_checker()
        if not seat_checker:
            return False
        rh_org_id = self.organization.id if self.organization else None
        return seat_checker.rh_org_has_subscription(rh_org_id)
