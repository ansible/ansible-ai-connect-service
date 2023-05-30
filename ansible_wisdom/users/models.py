import os
import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from django_prometheus.models import ExportModelOperationsMixin


class User(ExportModelOperationsMixin('user'), AbstractUser):
    uuid = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    date_terms_accepted = models.DateTimeField(unique=False, default=None, null=True)
