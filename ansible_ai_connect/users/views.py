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
from django.forms import Form
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.timezone import now
from django.views.generic import TemplateView
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from ansible_ai_connect.ai.api.aws.exceptions import (
    WcaSecretManagerMissingCredentialsError,
)
from ansible_ai_connect.ai.api.aws.wca_secret_manager import Suffixes
from ansible_ai_connect.main.cache.cache_per_user import cache_per_user
from ansible_ai_connect.users.models import Plan

from .serializers import UserResponseSerializer

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

    def dispatch(self, request, *args, **kwargs):
        self.org_has_api_key = None
        if (
            self.secret_manager
            and self.request.user.is_authenticated
            and self.request.user.rh_org_has_subscription
            and not self.request.user.is_aap_user()
        ):
            self.org_has_api_key = self.secret_manager.secret_exists(
                self.request.user.organization.id, Suffixes.API_KEY
            )

        if (
            settings.ANSIBLE_AI_ENABLE_ONE_CLICK_TRIAL
            and self.request.user.is_authenticated
            and self.request.user.is_oidc_user
            and self.request.user.rh_org_has_subscription
            and not self.org_has_api_key
        ):
            return HttpResponseRedirect(reverse("trial"))

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["use_tech_preview"] = settings.ANSIBLE_AI_ENABLE_TECH_PREVIEW
        context["deployment_mode"] = settings.DEPLOYMENT_MODE
        context["project_name"] = settings.ANSIBLE_AI_PROJECT_NAME
        context["org_has_api_key"] = self.org_has_api_key

        context["documentation_url"] = settings.COMMERCIAL_DOCUMENTATION_URL

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


class TermsOfService(TemplateView):
    template_name = "users/community-terms.html"

    def post(self, request, *args, **kwargs):
        form = Form(request.POST)
        form.is_valid()

        if request.POST.get("accepted") == "True":
            request.user.commercial_terms_accepted = now()
            request.session.save()

        return HttpResponseRedirect(reverse("home"))


class TrialView(TemplateView):
    template_name = "users/trial.html"

    def dispatch(self, request, *args, **kwargs):
        if settings.ANSIBLE_AI_ENABLE_ONE_CLICK_TRIAL:
            return super().dispatch(request, *args, **kwargs)
        return HttpResponseForbidden()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        has_active_plan = None
        has_expired_plan = None

        if hasattr(user, "userplan_set"):
            for up in user.userplan_set.all():
                if up.is_active:
                    has_active_plan = up
                else:
                    has_expired_plan = up

        context["project_name"] = settings.ANSIBLE_AI_PROJECT_NAME
        context["deployment_mode"] = settings.DEPLOYMENT_MODE
        context["has_active_plan"] = has_active_plan
        context["has_expired_plan"] = has_expired_plan
        context["accept_trial_terms"] = self.request.POST.get("accept_trial_terms") in [
            "True",
            "on",
        ]
        context["start_trial_button"] = self.request.POST.get("start_trial_button") == "True"

        return context

    def post(self, request, *args, **kwargs):
        form = Form(request.POST)
        form.is_valid()

        accept_trial_terms = request.POST.get("accept_trial_terms") == "on"
        start_trial_button = request.POST.get("start_trial_button") == "True"

        if start_trial_button and accept_trial_terms:
            trial_plan, _ = Plan.objects.get_or_create(
                name="trial of 90 days", expires_after="90 days"
            )
            request.user.plans.add(trial_plan)

        context = self.get_context_data(**kwargs)
        return render(request, self.template_name, context=context)


class TrialTermsOfService(TemplateView):
    template_name = "users/trial/terms.html"

    def post(self, request, *args, **kwargs):
        form = Form(request.POST)
        form.is_valid()

        return HttpResponseRedirect(reverse("trial"))
