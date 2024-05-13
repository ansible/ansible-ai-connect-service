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
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from social_django.utils import load_strategy

from ansible_ai_connect.ai.api.aws.exceptions import (
    WcaSecretManagerMissingCredentialsError,
)
from ansible_ai_connect.ai.api.aws.wca_secret_manager import Suffixes
from ansible_ai_connect.main.cache.cache_per_user import cache_per_user

from .serializers import UserResponseSerializer

ME_USER_CACHE_TIMEOUT_SEC = settings.ME_USER_CACHE_TIMEOUT_SEC
logger = logging.getLogger(__name__)


class HomeView(TemplateView):
    template_name = 'users/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["use_tech_preview"] = settings.ANSIBLE_AI_ENABLE_TECH_PREVIEW
        context["deployment_mode"] = settings.DEPLOYMENT_MODE
        context["project_name"] = settings.ANSIBLE_AI_PROJECT_NAME

        try:
            secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        except WcaSecretManagerMissingCredentialsError:
            return context

        if (
            self.request.user.is_authenticated
            and self.request.user.rh_org_has_subscription
            and not self.request.user.is_aap_user()
        ):
            org_has_api_key = secret_manager.secret_exists(
                self.request.user.organization.id, Suffixes.API_KEY
            )
            context["org_has_api_key"] = org_has_api_key

        if settings.ANSIBLE_AI_ENABLE_TECH_PREVIEW and not (
            self.request.user.is_authenticated and self.request.user.rh_user_has_seat
        ):
            context["documentation_url"] = settings.DOCUMENTATION_URL
        else:
            context["documentation_url"] = settings.COMMERCIAL_DOCUMENTATION_URL

        return context


class UnauthorizedView(TemplateView):
    template_name = 'users/unauthorized.html'
    extra_context = {'signup_url': settings.SIGNUP_URL}


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
        if organization:
            user_data["org_telemetry_opt_out"] = organization.telemetry_opt_out

        return Response(user_data)


class TermsOfService(TemplateView):
    template_name = None  # passed in via the urlpatterns
    extra_context = {
        'form': Form(),
    }

    def get(self, request, *args, **kwargs):
        partial_token = request.GET.get('partial_token')
        self.extra_context['partial_token'] = partial_token
        if partial_token is None:
            logger.warning('GET TermsOfService was invoked without partial_token')
            return HttpResponseForbidden()
        return super().get(request, args, kwargs)

    def post(self, request, *args, **kwargs):
        form = Form(request.POST)
        form.is_valid()
        partial_token = form.data.get('partial_token')
        if partial_token is None:
            logger.warning('POST TermsOfService was invoked without partial_token')
            return HttpResponseBadRequest()

        strategy = load_strategy()
        partial = strategy.partial_load(partial_token)
        if partial is None:
            logger.error('strategy.partial_load(partial_token) returned None')
            return HttpResponseBadRequest()

        accepted = request.POST.get('accepted') == 'True'
        request.session['terms_accepted'] = accepted
        request.session.save()

        backend = partial.backend
        complete = reverse("social:complete", kwargs={"backend": backend})
        return strategy.redirect(complete + f"?partial_token={partial.token}")
