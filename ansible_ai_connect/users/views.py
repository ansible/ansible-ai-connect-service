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

from ansible_base.lib.utils.schema import extend_schema_if_available
from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.forms import Form
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from ansible_ai_connect.ai.api.aws.exceptions import (
    WcaSecretManagerMissingCredentialsError,
)
from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    ModelPipelineStreamingChatBot,
)
from ansible_ai_connect.ai.api.telemetry import schema1
from ansible_ai_connect.ai.api.telemetry import schema2_utils as schema2
from ansible_ai_connect.ai.api.utils.segment import send_schema1_event
from ansible_ai_connect.main.cache.cache_per_user import cache_per_user
from ansible_ai_connect.users.constants import TRIAL_PLAN_NAME
from ansible_ai_connect.users.models import Plan
from ansible_ai_connect.users.one_click_trial import OneClickTrial

from .serializers import MarkdownUserResponseSerializer, UserResponseSerializer

ME_USER_CACHE_TIMEOUT_SEC = settings.ME_USER_CACHE_TIMEOUT_SEC
logger = logging.getLogger(__name__)


class HomeView(TemplateView):
    template_name = "users/home.html"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.secret_manager = None
        try:
            self.secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        except WcaSecretManagerMissingCredentialsError:
            pass

        # Check authentication has been configured
        match settings.DEPLOYMENT_MODE:
            case "saas":
                self.is_auth_configured = (
                    settings.SOCIAL_AUTH_OIDC_OIDC_ENDPOINT
                    and settings.SOCIAL_AUTH_OIDC_KEY
                    and settings.SOCIAL_AUTH_OIDC_SECRET
                )
            case "onprem":
                self.is_auth_configured = (
                    settings.AAP_API_URL
                    and settings.SOCIAL_AUTH_AAP_KEY
                    and settings.SOCIAL_AUTH_AAP_SECRET
                )
            case "upstream":
                self.is_auth_configured = (
                    settings.SOCIAL_AUTH_GITHUB_KEY or settings.SOCIAL_AUTH_GITHUB_TEAM_KEY
                )
            case _:
                self.is_auth_configured = True

    def dispatch(self, request, *args, **kwargs):
        self.org_has_api_key = None
        if (
            self.secret_manager
            and self.request.user.is_authenticated
            and self.request.user.rh_org_has_subscription
            and not self.request.user.is_aap_user()
        ):
            self.org_has_api_key = request.user.organization.has_api_key

        if (
            settings.ANSIBLE_AI_ENABLE_ONE_CLICK_TRIAL
            and self.request.user.is_authenticated
            and self.request.user.is_oidc_user
            and self.request.user.rh_org_has_subscription
            and not self.org_has_api_key
            and not self.request.user.rh_user_is_org_admin
        ):
            return HttpResponseRedirect(reverse("trial"))

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["use_tech_preview"] = settings.ANSIBLE_AI_ENABLE_TECH_PREVIEW
        context["deployment_mode"] = settings.DEPLOYMENT_MODE
        context["project_name"] = settings.ANSIBLE_AI_PROJECT_NAME
        context["org_has_api_key"] = self.org_has_api_key
        context["is_auth_configured"] = self.is_auth_configured

        context["documentation_url"] = settings.COMMERCIAL_DOCUMENTATION_URL

        # Show chatbot link when the chatbot service is configured.
        llm: ModelPipelineStreamingChatBot = apps.get_app_config("ai").get_model_pipeline(
            ModelPipelineStreamingChatBot
        )
        context["chatbot_enabled"] = (
            llm.config.inference_url and llm.config.model_id and settings.CHATBOT_DEFAULT_PROVIDER
        )

        return context


class UnauthorizedView(TemplateView):
    template_name = "users/unauthorized.html"
    extra_context = {"signup_url": settings.SIGNUP_URL}


class CurrentUserView(RetrieveAPIView):
    class MeRateThrottle(UserRateThrottle):
        scope = "me"

    permission_classes = [IsAuthenticated]
    serializer_class = UserResponseSerializer
    throttle_classes = [MeRateThrottle]

    @method_decorator(cache_per_user(ME_USER_CACHE_TIMEOUT_SEC))
    @extend_schema_if_available(
        extensions={"x-ai-description": "Retrieve current user information"}
    )
    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)

    def get_object(self):
        return self.request.user

    def retrieve(self, request, *args, **kwargs):
        # User data and use Django to serialise it into a dict
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        user_data = serializer.data

        # Enrich with Organisational data, if necessary
        organization = self.request.user.organization
        user_data["org_telemetry_opt_out"] = (
            organization.has_telemetry_opt_out if organization else True
        )

        return Response(user_data)


class MarkdownCurrentUserView(RetrieveAPIView):
    class MeRateThrottle(UserRateThrottle):
        scope = "me"

    permission_classes = [IsAuthenticated]
    serializer_class = MarkdownUserResponseSerializer
    throttle_classes = [MeRateThrottle]

    @method_decorator(cache_per_user(ME_USER_CACHE_TIMEOUT_SEC))
    @extend_schema_if_available(extensions={"x-ai-description": "Retrieve current logged in user"})
    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)

    def get_object(self):
        return self.request.user

    def retrieve(self, request, *args, **kwargs):
        # User data and use Django to serialise it into a dict
        instance = self.get_object()
        serializer = self.get_serializer(instance, context={"request": request})

        response = serializer.data

        return Response(response, content_type="application/json")


class TrialView(TemplateView):
    template_name = "users/trial.html"
    permission_classes = [IsAuthenticated]

    def get_trial_plan(self):
        trial_plan, _ = Plan.objects.get_or_create(name=TRIAL_PLAN_NAME, expires_after="90 days")
        return trial_plan

    def dispatch(self, request, *args, **kwargs):
        if isinstance(request.user, AnonymousUser):
            return HttpResponseRedirect(reverse("login"))

        if any(up.plan == self.get_trial_plan() for up in request.user.userplan_set.all()):
            return super().dispatch(request, *args, **kwargs)

        if not settings.ANSIBLE_AI_ENABLE_ONE_CLICK_TRIAL:
            return HttpResponseForbidden()

        if not self.request.user.rh_org_has_subscription:
            return HttpResponseForbidden(
                "Your organization doesn't have an active "
                "Ansible Automation Platform subscription."
            )

        if request.user.organization.has_api_key:
            return HttpResponseForbidden(
                "You and the user of your organization cannot "
                "use the Trial because an api_key was set."
            )

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        one_click_trial = OneClickTrial(user)
        has_active_plan, has_expired_plan, days_left = one_click_trial.get_plans()

        context["one_click_trial_available"] = one_click_trial.is_available()
        context["project_name"] = settings.ANSIBLE_AI_PROJECT_NAME
        context["deployment_mode"] = settings.DEPLOYMENT_MODE
        context["has_active_plan"] = has_active_plan
        context["days_left"] = days_left
        context["has_expired_plan"] = has_expired_plan
        context["accept_trial_terms"] = self.request.POST.get("accept_trial_terms") in [
            "True",
            "on",
        ]
        # "accept_trial_terms" and "allow_information_share" are merged into one checkbox
        context["allow_information_share"] = context["accept_trial_terms"]
        context["accept_marketing_emails"] = self.request.POST.get("accept_marketing_emails") in [
            "True",
            "on",
        ]
        context["start_trial_button"] = self.request.POST.get("start_trial_button") == "True"

        return context

    def post(self, request, *args, **kwargs):
        form = Form(request.POST)
        form.is_valid()

        accept_trial_terms = request.POST.get("accept_trial_terms") == "on"
        # "accept_trial_terms" and "allow_information_share" are merged into one checkbox
        allow_information_share = accept_trial_terms
        start_trial_button = request.POST.get("start_trial_button") == "True"
        accept_marketing_emails = request.POST.get("accept_marketing_emails") == "on"

        # The user already have a trial plan, we do nothing
        user_has_trial_already = any(
            up.plan == self.get_trial_plan() for up in request.user.userplan_set.all()
        )

        if (
            not user_has_trial_already
            and start_trial_button
            and accept_trial_terms
            and allow_information_share
        ):
            request.user.plans.add(self.get_trial_plan())

            if accept_marketing_emails:
                up = request.user.userplan_set.filter(plan=self.get_trial_plan()).first()
                up.accept_marketing = True
                up.save()
            event = schema1.OneClickTrialStartedEvent()
            event.set_request(request)
            send_schema1_event(event)

            schema2.oneclick_trial_event_send(request.user)

        context = self.get_context_data(**kwargs)
        return render(request, self.template_name, context=context)
