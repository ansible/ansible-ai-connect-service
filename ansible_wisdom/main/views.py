#!/usr/bin/env python3

import logging

from ai.api.permissions import (
    AcceptedTermsPermission,
    IsOrganisationAdministrator,
    IsOrganisationLightspeedSubscriber,
    IsWCAKeyApiFeatureFlagOn,
    IsWCAModelIdApiFeatureFlagOn,
)
from django.contrib.auth import views as auth_views
from django.http import HttpResponseRedirect
from main.base_views import ProtectedTemplateView
from oauth2_provider.contrib.rest_framework import IsAuthenticatedOrTokenHasScope
from rest_framework.permissions import IsAuthenticated

logger = logging.getLogger(__name__)


class LoginView(auth_views.LoginView):
    def dispatch(self, request, *args, **kwargs):
        if self.request.user.is_authenticated:
            return HttpResponseRedirect("/")
        return super().dispatch(request, *args, **kwargs)


class ConsoleView(ProtectedTemplateView):
    template_name = 'console/console.html'

    permission_classes = [
        IsWCAKeyApiFeatureFlagOn,
        IsWCAModelIdApiFeatureFlagOn,
        IsAuthenticated,
        IsAuthenticatedOrTokenHasScope,
        IsOrganisationAdministrator,
        IsOrganisationLightspeedSubscriber,
        AcceptedTermsPermission,
    ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user:
            context["user_name"] = self.request.user.username
        return context
