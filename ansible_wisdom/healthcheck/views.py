import json

from django.http import HttpResponse
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


class WisdomServiceHealthView(APIView):
    """
    Wisdom Service Health Check
    """

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def __init__(self):
        self.mainView = MainView()

    @extend_schema(
        responses={
            200: OpenApiTypes.OBJECT,
            500: OpenApiResponse(description='One or more backend services are unavailable.'),
        },
        examples=[
            OpenApiExample(
                name="Example output",
                value={
                    "Cache backend: default": "working",
                    "DatabaseBackend": "working",
                    "ModelServerHealthCheck": "working",
                    "RedisHealthCheck": "working",
                },
                response_only=True,
            )
        ],
        methods=['GET'],
        summary="Health check with backend server status",
    )
    @method_decorator(cache_page(60))
    def get(self, request, *args, **kwargs):
        # Force to return JSON data
        # request.META['HTTP_ACCEPT'] = 'application/json'
        self.mainView.request = request
        return self.mainView.get(request, *args, **kwargs)


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
