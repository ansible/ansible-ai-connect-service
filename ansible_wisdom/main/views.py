#!/usr/bin/env python3

import logging

from django.contrib.auth import views as auth_views
from django.http import HttpResponseRedirect

logger = logging.getLogger(__name__)


class LoginView(auth_views.LoginView):
    def dispatch(self, request, *args, **kwargs):
        if self.request.user.is_authenticated:
            return HttpResponseRedirect("/")
        return super().dispatch(request, *args, **kwargs)
