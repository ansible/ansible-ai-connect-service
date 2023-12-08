#!/usr/bin/env python3

import logging

from ai.api.permissions import (
    AcceptedTermsPermission,
    IsOrganisationAdministrator,
    IsOrganisationLightspeedSubscriber,
)
from django.conf import settings
from django.contrib.auth import views as auth_views
from django.http import HttpResponseRedirect
from main.base_views import ProtectedTemplateView
from main.settings.base import SOCIAL_AUTH_OIDC_KEY
from oauth2_provider.contrib.rest_framework import IsAuthenticatedOrTokenHasScope
from rest_framework.permissions import IsAuthenticated

logger = logging.getLogger(__name__)


class LoginView(auth_views.LoginView):
    def dispatch(self, request, *args, **kwargs):
        if self.request.user.is_authenticated:
            return HttpResponseRedirect("/")
        return super().dispatch(request, *args, **kwargs)


class LogoutView(auth_views.LogoutView):
    def dispatch(self, request, *args, **kwargs):
        self.next_page = self.get_next_page(request)
        return super().dispatch(request, *args, **kwargs)

    def get_next_page(self, request):
        rht = (
            'https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/logout'
            f'?post_logout_redirect_uri={request.build_absolute_uri("/")}'
            f'&client_id={SOCIAL_AUTH_OIDC_KEY}'
        )

        return rht if request.user.is_oidc_user() else None


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
        if self.request.user:
            context["user_name"] = self.request.user.username
            context["rh_org_has_subscription"] = self.request.user.rh_org_has_subscription
            context["telemetry_opt_enabled"] = settings.ADMIN_PORTAL_TELEMETRY_OPT_ENABLED
        return context
