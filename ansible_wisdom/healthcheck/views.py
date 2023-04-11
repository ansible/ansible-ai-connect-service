import json
from datetime import datetime

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page, never_cache
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    OpenApiTypes,
    extend_schema,
)
from health_check.views import MainView
from rest_framework import permissions
from rest_framework.views import APIView

from .version_info import VersionInfo


class HealthCheckCustomView(MainView):
    _plugin_name_map = {
        'Cache backend: default': 'cache',
        'DatabaseBackend': 'db',
        'ModelServerHealthCheck': 'model-server',
    }

    _version_info = VersionInfo()

    def get(self, request, *args, **kwargs):
        status_code = 500 if self.errors else 200
        return self.render_to_response_json(self.plugins, status_code)

    def render_to_response_json(self, plugins, status):  # customize JSON output
        data = {
            'status': 'ok' if status == 200 else 'error',
            'timestamp': str(datetime.now().isoformat()),
            'version': self._version_info.image_tags,
            'git_commit': self._version_info.git_commit,
            'model_name': settings.ANSIBLE_AI_MODEL_NAME,
        }
        dependencies = []
        for p in plugins:
            plugins_id = self._plugin_name_map.get(p.identifier(), 'unknown')
            plugin_status = str(p.pretty_status()) if p.errors else 'ok'
            time_taken = round(p.time_taken * 1000, 3)
            dependencies.append(
                {'name': plugins_id, 'status': plugin_status, 'time_taken': time_taken}
            )

        data['dependencies'] = dependencies

        return JsonResponse(data, status=status)


class WisdomServiceHealthView(APIView):
    """
    Wisdom Service Health Check
    """

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def __init__(self):
        super().__init__()
        self.customView = HealthCheckCustomView()

    @extend_schema(
        responses={
            200: OpenApiTypes.OBJECT,
            500: OpenApiResponse(description='One or more backend services are unavailable.'),
        },
        examples=[
            OpenApiExample(
                name="Example output",
                value={
                    "status": "ok",
                    "timestamp": "2023-03-13T17:25:17.240683",
                    "version": "latest 0.1.202303131417",
                    "git_commit": "b987bc43b90f8aca2deaf3bda85596f4b95a10a0",
                    "model_name": "ansible-wisdom-v09",
                    "dependencies": [
                        {"name": "cache", "status": "ok", "time_taken": 2.032},
                        {"name": "db", "status": "ok", "time_taken": 233.538},
                        {"name": "model-server", "status": "ok", "time_taken": 0.001},
                    ],
                },
                response_only=True,
            )
        ],
        methods=['GET'],
        summary="Health check with backend server status",
    )
    @method_decorator(cache_page(60))
    def get(self, request, *args, **kwargs):
        return self.customView.get(request, *args, **kwargs)


class WisdomServiceLivenessProbeView(APIView):
    """
    Wisdom Service Liveness Probe View
    """

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    @extend_schema(
        responses={
            200: OpenApiResponse(description='OK'),
        },
        summary="Liveness probe",
    )
    @method_decorator(never_cache)
    def get(self, request, *args, **kwargs):
        data = {'status': 'ok'}
        data_json = json.dumps(data)
        return HttpResponse(data_json, content_type='application/json')
