from django.db import models  # noqa
from django.utils.translation import gettext_lazy as _

from .api.model_client.grpc_client import GrpcClient
from .api.model_client.http_client import HttpClient
from .api.model_client.mock_client import MockClient


class ModelMeshType(models.TextChoices):
    GRPC = "grpc", GrpcClient, _("gRPC")
    HTTP = "http", HttpClient, _("HTTP")
    MOCK = "mock", MockClient, _("Mock")

    def __new__(cls, name, client):
        obj = str.__new__(cls, name)
        obj._value_ = name
        obj._client_ = client
        return obj

    @property
    def client(self):
        return self._client_


class AIModel(models.Model):
    name = models.CharField(max_length=255, unique=True)
    version = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    model_mesh_api_type = models.CharField(
        max_length=4, choices=ModelMeshType.choices, default=ModelMeshType.HTTP
    )
    inference_url = models.URLField()
    management_url = models.URLField()

    def __str__(self):
        return self.name
