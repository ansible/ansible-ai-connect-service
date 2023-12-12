import logging

from django.db import models

logger = logging.getLogger(__name__)


class Organization(models.Model):
    id = models.IntegerField(primary_key=True)
    telemetry_opt_out = models.BooleanField(default=False)
