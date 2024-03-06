#!/usr/bin/env python3

import logging

from django.conf import settings
from django.contrib.auth import views as auth_views
from django.http import HttpResponseRedirect
from oauth2_provider.contrib.rest_framework import IsAuthenticatedOrTokenHasScope
from rest_framework.permissions import IsAuthenticated

from ansible_wisdom.ai.api.permissions import (
    AcceptedTermsPermission,
    IsOrganisationAdministrator,
    IsOrganisationLightspeedSubscriber,
)
from ansible_wisdom.main.base_views import ProtectedTemplateView
from ansible_wisdom.main.settings.base import SOCIAL_AUTH_OIDC_KEY

logger = logging.getLogger(__name__)


class LoginView(auth_views.LoginView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['use_github_team'] = settings.USE_GITHUB_TEAM
        context["use_tech_preview"] = settings.ANSIBLE_AI_ENABLE_TECH_PREVIEW
        return context

    def dispatch(self, request, *args, **kwargs):
        if self.request.user.is_authenticated:
            return HttpResponseRedirect("/")
        return super().dispatch(request, *args, **kwargs)


class LogoutView(auth_views.LogoutView):
    def dispatch(self, request, *args, **kwargs):
        self.next_page = self.get_next_page(request)
        return super().dispatch(request, *args, **kwargs)

    def get_next_page(self, request):
        next_url = request.build_absolute_uri("/")
        if request.user.is_oidc_user():
            return (
                'https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/logout'
                f'?post_logout_redirect_uri={next_url}'
                f'&client_id={SOCIAL_AUTH_OIDC_KEY}'
            )

        if request.user.is_aap_user():
            return f'{settings.AAP_API_URL}/logout/?next={next_url}'

        return None


class ConsoleView(ProtectedTemplateView):
    template_name = 'console/console.html'

    # Permission checks for the following are handled when the template selection is made.
    # - IsOrganisationAdministrator,
    # - IsOrganisationLightspeedSubscriber,
    permission_classes = [
        IsAuthenticated,
        IsAuthenticatedOrTokenHasScope,
        AcceptedTermsPermission,
    ]

    def get_template_names(self):
        if not IsOrganisationAdministrator().has_permission(self.request, self):
            return ["console/denied.html"]

        if not IsOrganisationLightspeedSubscriber().has_permission(self.request, self):
            return ["console/denied.html"]

        return super().get_template_names()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        if user:
            context["user_name"] = user.username
            context["rh_org_has_subscription"] = user.rh_org_has_subscription
            organization = user.organization
            if organization:
                is_schema_2_telemetry_enabled = organization.is_schema_2_telemetry_enabled
                context["telemetry_schema_2_enabled"] = is_schema_2_telemetry_enabled

                if is_schema_2_telemetry_enabled:
                    context[
                        "telemetry_schema_2_admin_dashboard_url"
                    ] = settings.TELEMETRY_ADMIN_DASHBOARD_URL

        return context
