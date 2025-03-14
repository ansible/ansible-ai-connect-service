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

import json
import logging
from datetime import datetime

import requests
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

from ansible_ai_connect.healthcheck.backends import BaseLightspeedHealthCheck

from .version_info import VersionInfo

logger = logging.getLogger(__name__)
CACHE_TIMEOUT = 30
_version_info = VersionInfo()


def common_data():
    data = {
        "timestamp": str(datetime.now().isoformat()),
        "version": _version_info.image_tags,
        "git_commit": _version_info.git_commit,
    }
    deployed_region = settings.DEPLOYED_REGION
    # Only include 'deployed_region' if set
    if deployed_region:
        data = {**data, "deployed_region": deployed_region}
    return data


class HealthCheckCustomView(MainView):

    from ansible_ai_connect.ai.api.model_pipelines.pipelines import ModelPipeline
    from ansible_ai_connect.ai.api.model_pipelines.registry import REGISTRY_ENTRY

    _plugin_name_map = {
        "DatabaseBackend": "db",
        "AWSSecretManagerHealthCheck": "secret-manager",
        "AuthorizationHealthCheck": "authorization",
    }
    for pipeline in REGISTRY_ENTRY.keys():
        if issubclass(pipeline, ModelPipeline):
            _plugin_name_map[pipeline.__name__] = pipeline.alias()

    @method_decorator(cache_page(CACHE_TIMEOUT))
    def get(self, request, *args, **kwargs):
        status_code = 200  # Set status code to 200 for letting the output be cached
        return self.render_to_response_json(self.plugins, status_code, request.user)

    def render_to_response_json(self, plugins, status, user):  # customize JSON output
        data = common_data()
        data["status"] = "error" if self.errors else "ok"

        dependencies = []
        for p in plugins:
            plugins_id = self._plugin_name_map.get(p.identifier(), "unknown")
            if isinstance(p, BaseLightspeedHealthCheck):
                plugin_status = p.pretty_status()
            else:
                plugin_status = str(p.pretty_status()) if p.errors else "ok"
            time_taken = round(p.time_taken * 1000, 3)
            plugin_data = {"name": plugins_id, "status": plugin_status, "time_taken": time_taken}
            if not p.status:
                logger.error(f"HEALTH CHECK ERROR: {json.dumps(plugin_data)}")
            dependencies.append(plugin_data)

        data["dependencies"] = dependencies

        return JsonResponse(data, status=status)


class WisdomServiceHealthView(APIView):
    """
    Service Health Check
    """

    permission_classes = [permissions.AllowAny]

    def __init__(self):
        super().__init__()
        self.customView = HealthCheckCustomView()

    @extend_schema(
        responses={
            200: OpenApiTypes.OBJECT,
            500: OpenApiResponse(description="One or more backend services are unavailable."),
        },
        examples=[
            OpenApiExample(
                name="Example output",
                value={
                    "status": "ok",
                    "timestamp": "2023-03-13T17:25:17.240683",
                    "version": "latest 0.1.202303131417",
                    "git_commit": "b987bc43b90f8aca2deaf3bda85596f4b95a10a0",
                    "deployed_region": "dev",
                    "dependencies": [
                        {"name": "db", "status": "ok", "time_taken": 233.538},
                        {"name": "model-server", "status": "ok", "time_taken": 0.001},
                    ],
                },
                response_only=True,
            )
        ],
        methods=["GET"],
        summary="Health check with backend server status",
    )
    def get(self, request, *args, **kwargs):
        res = self.customView.get(request, *args, **kwargs)
        # res contains status_code = 200 for utilizing view cache.  We need to set the correct
        # status code based on the status attribute stored in the JSON content
        data = json.loads(res.content)
        if data["status"] != "ok":
            res.status_code = 500
        return res


class WisdomServiceLivenessProbeView(APIView):
    """
    Service Liveness Probe View
    """

    permission_classes = [permissions.AllowAny]

    @extend_schema(
        responses={
            200: OpenApiResponse(description="OK"),
        },
        summary="Liveness probe",
    )
    @method_decorator(never_cache)
    def get(self, request, *args, **kwargs):

        # TODO: PoC.
        # TODO: This /health endpoint is being called either
        #  by the AAP health (no user authenticated),
        #  also when calling from the client after being authenticated in AAP.
        aap_jwt = request._request.headers.get("X-DAB-JW-TOKEN")
        if aap_jwt is not None:
            response = requests.post(
                url="http://127.0.0.1:8085/v1/query",
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "X-DAB-JW-TOKEN": aap_jwt,
                },
                json={"query": "write a deployment yaml for the mongodb image"},
                verify=False,
            )
            print(str(response))

        data = common_data()
        data["status"] = "ok"
        data_json = json.dumps(data)
        return HttpResponse(data_json, content_type="application/json")
