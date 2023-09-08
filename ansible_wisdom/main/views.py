#!/usr/bin/env python3

import logging

from django.contrib.auth import views as auth_views
from django.http import HttpResponseRedirect

from ai.api.permissions import (
    AcceptedTermsPermission,
    IsOrganisationAdministrator,
    IsOrganisationLightspeedSubscriber,
    IsWCAKeyApiFeatureFlagOn,
    IsWCAModelIdApiFeatureFlagOn,
)
from django.conf import settings
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

    if settings.DEBUG:
        permission_classes = [
            IsAuthenticated,
            IsAuthenticatedOrTokenHasScope,
            AcceptedTermsPermission,
        ]
    else:
        permission_classes = [
            IsWCAKeyApiFeatureFlagOn,
            IsWCAModelIdApiFeatureFlagOn,
            IsAuthenticated,
            IsAuthenticatedOrTokenHasScope,
            IsOrganisationAdministrator,
            IsOrganisationLightspeedSubscriber,
            AcceptedTermsPermission,
        ]
