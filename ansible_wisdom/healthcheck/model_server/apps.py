from django.apps import AppConfig
from health_check.plugins import plugin_dir


class ModelServerAppConfig(AppConfig):
    name = 'healthcheck.model_server'

    def ready(self):
        from .backends import ModelServerHealthCheck

        plugin_dir.register(ModelServerHealthCheck)
