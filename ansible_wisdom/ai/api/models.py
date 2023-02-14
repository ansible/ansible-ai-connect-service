"""
Models to be used for input/output validations.
"""
from django.contrib.postgres import fields
from django.db import models


class CompletionRequest(models.Model):
    """Model for completion request received from Ansible VS Code extension."""

    class Meta:
        managed = False  # Do not create database tables for this model

    context = models.TextField()
    prompt = models.TextField(null=True)
    userId = models.UUIDField(null=True)
    suggestionId = models.UUIDField(null=True)


class CompletionResponse(models.Model):
    """Model for predictions response received from model server."""

    class Meta:
        managed = False  # Do not create database tables for this model

    predictions = fields.ArrayField(models.TextField())
