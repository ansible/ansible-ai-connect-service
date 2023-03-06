from django.db import models  # noqa
from django.utils.translation import gettext_lazy as _


class AIModel(models.Model):
    class ModelMeshType(models.TextChoices):
        GRPC = "grpc", _("gRPC")
        HTTP = "http", _("HTTP")

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
