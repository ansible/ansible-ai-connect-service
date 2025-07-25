#!/usr/bin/env python3

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

import logging

from django.apps import apps
from django.conf import settings
from django.contrib.auth import views as auth_views
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponseRedirect
from django.utils.http import url_has_allowed_host_and_scheme
from django_prometheus.exports import ExportToDjangoView
from oauth2_provider.contrib.rest_framework import IsAuthenticatedOrTokenHasScope
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.renderers import BaseRenderer
from rest_framework.views import APIView

from ansible_ai_connect.ai.api.model_pipelines.nop.pipelines import (
    NopChatBotPipeline,
    NopStreamingChatBotPipeline,
)
from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    ModelPipelineChatBot,
    ModelPipelineStreamingChatBot,
)
from ansible_ai_connect.ai.api.permissions import (
    IsOrganisationAdministrator,
    IsOrganisationLightspeedSubscriber,
)
from ansible_ai_connect.main.base_views import ProtectedTemplateView
from ansible_ai_connect.main.permissions import IsAAPUser, IsRHInternalUser, IsTestUser
from ansible_ai_connect.main.settings.base import SOCIAL_AUTH_OIDC_KEY

logger = logging.getLogger(__name__)


class LoginView(auth_views.LoginView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["next"] = self.request.GET.get("next")
        context["deployment_mode"] = settings.DEPLOYMENT_MODE
        context["project_name"] = settings.ANSIBLE_AI_PROJECT_NAME
        context["aap_api_provider_name"] = settings.AAP_API_PROVIDER_NAME
        context["documentation_url"] = settings.COMMERCIAL_DOCUMENTATION_URL
        return context

    def dispatch(self, request, *args, **kwargs):
        if self.request.user.is_authenticated:
            next_url = self.request.GET.get("next", "/")
            if url_has_allowed_host_and_scheme(
                next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
            ):
                return HttpResponseRedirect(next_url)
            return HttpResponseRedirect("/")
        return super().dispatch(request, *args, **kwargs)


class LogoutView(auth_views.LogoutView):
    def dispatch(self, request, *args, **kwargs):
        self.next_page = self.get_next_page(request)
        return super().dispatch(request, *args, **kwargs)

    def get_next_page(self, request):
        if isinstance(request.user, AnonymousUser):
            return None

        next_url = request.build_absolute_uri("/")
        if request.user.is_oidc_user():
            return (
                "https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/logout"
                f"?post_logout_redirect_uri={next_url}"
                f"&client_id={SOCIAL_AUTH_OIDC_KEY}"
            )

        if request.user.is_aap_user():
            return f"{settings.AAP_API_URL}/logout/?next={next_url}"

        return None


class ConsoleView(ProtectedTemplateView):
    template_name = "console/console.html"

    # Permission checks for the following are handled when the template selection is made.
    # - IsOrganisationAdministrator,
    # - IsOrganisationLightspeedSubscriber,
    permission_classes = [
        IsAuthenticated,
        IsAuthenticatedOrTokenHasScope,
    ]

    def get_template_names(self):
        if not IsOrganisationAdministrator().has_permission(self.request, self):
            return ["console/denied.html"]

        if not IsOrganisationLightspeedSubscriber().has_permission(self.request, self):
            return ["console/denied.html"]

        return super().get_template_names()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["project_name"] = settings.ANSIBLE_AI_PROJECT_NAME
        user = self.request.user
        if user:
            context["user_name"] = user.username
            context["rh_org_has_subscription"] = user.rh_org_has_subscription
            organization = user.organization
            if organization:
                context["telemetry_schema_2_admin_dashboard_url"] = (
                    settings.TELEMETRY_ADMIN_DASHBOARD_URL
                )

        return context


class ChatbotView(ProtectedTemplateView):
    template_name = "chatbot/index.html"

    permission_classes = [
        IsAuthenticated,
        IsRHInternalUser | IsTestUser | IsAAPUser | IsOrganisationLightspeedSubscriber,
    ]

    chatbot_enabled: bool
    streaming_chatbot_enabled: bool

    def getModelPipelineChatBot(self):
        return apps.get_app_config("ai").get_model_pipeline(ModelPipelineChatBot)

    def getModelStreamingPipelineChatBot(self):
        return apps.get_app_config("ai").get_model_pipeline(ModelPipelineStreamingChatBot)

    def __init__(self):
        super().__init__()
        chat_llm = self.getModelPipelineChatBot()
        self.chatbot_enabled = (
            not isinstance(chat_llm, NopChatBotPipeline)
            and chat_llm.config.inference_url
            and chat_llm.config.model_id
            and settings.CHATBOT_DEFAULT_PROVIDER
        )
        streaming_chat_llm = self.getModelStreamingPipelineChatBot()
        self.streaming_chatbot_enabled = (
            not isinstance(streaming_chat_llm, NopStreamingChatBotPipeline)
            and streaming_chat_llm.config.inference_url
            and streaming_chat_llm.config.model_id
            and settings.CHATBOT_DEFAULT_PROVIDER
        )
        self.chatbot_enabled = self.chatbot_enabled or self.streaming_chatbot_enabled

    def get(self, request):
        # Open the chatbot page when the chatbot service is configured.
        if self.chatbot_enabled:
            return super().get(request)

        # Otherwise, redirect to the home page.
        return HttpResponseRedirect("/")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["bot_name"] = settings.ANSIBLE_AI_CHATBOT_NAME
        user = self.request.user
        if user and user.is_authenticated:
            context["user_name"] = user.username
        context["debug"] = "true" if settings.CHATBOT_DEBUG_UI else "false"
        context["stream"] = "true" if self.streaming_chatbot_enabled else "false"

        return context


class PlainTextRenderer(BaseRenderer):
    media_type = "text/plain"
    format = "txt"

    def render(self, data, media_type=None, renderer_context=None):
        if not isinstance(data, str):
            data = str(data)
        return data.encode(self.charset)


class MetricsView(APIView):
    schema = None

    renderer_classes = [PlainTextRenderer]

    def initialize_request(self, request, *args, **kwargs):
        if settings.ALLOW_METRICS_FOR_ANONYMOUS_USERS:
            self.permission_classes = (AllowAny,)
        drf_request = super().initialize_request(request, *args, **kwargs)
        return drf_request

    def get(self, request):
        if (
            settings.ALLOW_METRICS_FOR_ANONYMOUS_USERS
            or request.user.rh_aap_superuser
            or request.user.rh_aap_system_auditor
        ):
            return ExportToDjangoView(request)
        raise PermissionDenied()
