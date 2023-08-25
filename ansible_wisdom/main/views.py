#!/usr/bin/env python3

import logging

from django.contrib.auth import views as auth_views
from django.http import HttpResponseRedirect

from ai.api.permissions import (
    AcceptedTermsPermission,
    IsOrganisationAdministrator,
    IsOrganisationLightspeedSubscriber,
)
from django.views.generic import TemplateView
from rest_framework import exceptions
from rest_framework.permissions import IsAuthenticated

logger = logging.getLogger(__name__)


class LoginView(auth_views.LoginView):
    def dispatch(self, request, *args, **kwargs):
        if self.request.user.is_authenticated:
            return HttpResponseRedirect("/")
        return super().dispatch(request, *args, **kwargs)


class ConsoleView(TemplateView):
    template_name = 'console/console.html'

    permission_classes = [
        IsAuthenticated,
        # IsOrganisationAdministrator,
        # IsOrganisationLightspeedSubscriber,
        AcceptedTermsPermission,
    ]

    def get(self, request, *args, **kwargs):
        self.check_permissions(request)

        return super().get(request, *args, **kwargs)

    def get_permissions(self):
        return [permission() for permission in self.permission_classes]

    def check_permissions(self, request):
        for permission in self.get_permissions():
            if not permission.has_permission(request, self):
                raise exceptions.PermissionDenied()
