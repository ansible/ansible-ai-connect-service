from django.apps import AppConfig
from health_check.plugins import plugin_dir


class HealthCheckAppConfig(AppConfig):
    name = 'healthcheck'

    def ready(self):
        from .backends import ModelServerHealthCheck

        plugin_dir.register(ModelServerHealthCheck)
