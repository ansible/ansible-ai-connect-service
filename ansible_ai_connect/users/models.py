#  Copyright Red Hat
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import logging
import uuid

from ansible_base.lib.abstract_models import AbstractTeam
from ansible_base.resource_registry.fields import AnsibleResourceField
from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.utils.functional import cached_property
from django_deprecate_fields import deprecate_field
from django_prometheus.models import ExportModelOperationsMixin

from ansible_ai_connect.organizations.models import ExternalOrganization

from .constants import USER_SOCIAL_AUTH_PROVIDER_AAP, USER_SOCIAL_AUTH_PROVIDER_OIDC

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


class Plan(models.Model):
    name = models.CharField(max_length=80, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_after = models.DurationField(default=None, null=True)


class User(ExportModelOperationsMixin("user"), AbstractUser):
    uuid = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    community_terms_accepted = models.DateTimeField(default=None, null=True)
    commercial_terms_accepted = models.DateTimeField(default=None, null=True)
    organization_id = deprecate_field(models.IntegerField(default=None, null=True))
    organization = NonClashingForeignKey(
        ExternalOrganization,
        default=None,
        null=True,
        on_delete=models.CASCADE,
    )
    rh_user_is_org_admin = models.BooleanField(default=False)
    rh_internal = models.BooleanField(default=False)
    external_username = models.CharField(default="", null=False, max_length=150)
    name = models.CharField(default=None, null=True, max_length=150)
    given_name = models.CharField(default=None, null=True, max_length=150)
    family_name = models.CharField(default=None, null=True, max_length=150)
    email = models.CharField(default=None, null=True, max_length=150)
    email_verified = models.BooleanField(default=False, null=True)
    aap_user = models.BooleanField(default=False)

    class Meta:
        app_label = "users"

    @property
    def org_id(self) -> int | None:
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

        # user is of an on-prem AAP with valid license
        if self.is_aap_user():
            return self.rh_aap_licensed

        # Logic used during the transition and before the removal of the rh_user_has_seat attr
        if self.organization and self.rh_org_has_subscription:
            if not settings.ANSIBLE_AI_ENABLE_TECH_PREVIEW:
                return True

            return self.organization.has_api_key

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
        return self.is_aap_user() and self.social_auth.values()[0]["extra_data"]["aap_licensed"]

    @cached_property
    def rh_aap_system_auditor(self) -> bool:
        return (
            self.is_aap_user() and self.social_auth.values()[0]["extra_data"]["aap_system_auditor"]
        )

    @cached_property
    def rh_aap_superuser(self) -> bool:
        return self.is_aap_user() and self.social_auth.values()[0]["extra_data"]["aap_superuser"]

    plans = models.ManyToManyField(
        Plan,
        through="users.UserPlan",
        through_fields=("user", "plan"),
    )


class UserPlan(models.Model):
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    expired_at = models.DateTimeField(default=None, null=True)
    accept_marketing = models.BooleanField(default=False)

    def __init__(self, *args, **kwargs):
        if "plan_id" in kwargs:
            p = Plan.objects.get(id=kwargs["plan_id"])
            if p.expires_after:
                kwargs["expired_at"] = timezone.now() + p.expires_after
        super().__init__(*args, **kwargs)

    @property
    def is_active(self):
        if not self.expired_at:
            return True
        return self.expired_at > timezone.now()


class Team(AbstractTeam):
    """A Team compatible with Django Ansible Base Teams"""

    resource = AnsibleResourceField(primary_key_field="id")

    ignore_relations = []

    class Meta:
        app_label = "users"
        ordering = ["id"]
        abstract = False
