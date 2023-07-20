import os
import uuid

from django.apps import apps
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.functional import cached_property
from django_prometheus.models import ExportModelOperationsMixin


class User(ExportModelOperationsMixin('user'), AbstractUser):
    uuid = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    community_terms_accepted = models.DateTimeField(default=None, null=True)
    commercial_terms_accepted = models.DateTimeField(default=None, null=True)
    organization_id = models.IntegerField(default=None, null=True)

    @cached_property
    def has_seat(self) -> bool:
        if not self.social_auth.values():
            return False
        if self.social_auth.values()[0]["provider"] != "oidc":
            return False

        seat_checker = apps.get_app_config("ai").get_seat_checker()
        if not seat_checker:
            return False
        uid = self.social_auth.values()[0]["uid"]
        rh_org_id = self.organization_id
        return seat_checker.check(uid, self.username, rh_org_id)
