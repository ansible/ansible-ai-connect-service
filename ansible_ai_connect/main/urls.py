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

"""main URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from oauth2_provider.urls import app_name, base_urlpatterns

from ansible_ai_connect.ai.api.telemetry.api_telemetry_settings_views import (
    TelemetrySettingsView,
)
from ansible_ai_connect.healthcheck.views import (
    WisdomServiceHealthView,
    WisdomServiceLivenessProbeView,
)
from ansible_ai_connect.main.views import (
    ConsoleView,
    LoginView,
    LogoutView,
    MetricsView,
)
from ansible_ai_connect.users.views import (
    CurrentUserView,
    HomeView,
    TermsOfService,
    UnauthorizedView,
)

WISDOM_API_VERSION = "v0"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    # add the GitHub OAuth redirect URL /complete/github-team/
    path("", include("social_django.urls", namespace="social")),
    # Do not add a trailing slash. django_prometheus uses plain /metrics
    # Adding a trailing slash breaks our metric collection in all sorts of ways.
    path("metrics", MetricsView.as_view(), name="prometheus-metrics"),
    path("admin/", admin.site.urls),
    path(f"api/{WISDOM_API_VERSION}/ai/", include("ansible_ai_connect.ai.api.urls")),
    path(f"api/{WISDOM_API_VERSION}/me/", CurrentUserView.as_view(), name="me"),
    path("unauthorized/", UnauthorizedView.as_view(), name="unauthorized"),
    path("check/status/", WisdomServiceHealthView.as_view(), name="health_check"),
    path("check/", WisdomServiceLivenessProbeView.as_view(), name="liveness_probe"),
    path(
        "community-terms/",
        TermsOfService.as_view(template_name="users/community-terms.html"),
        name="community_terms",
    ),
    path("o/", include((base_urlpatterns, app_name), namespace="oauth2_provider")),
    path(
        "login/",
        LoginView.as_view(),
        name="login",
    ),
    path("logout/", LogoutView.as_view(), name="logout"),
]

if settings.DEBUG or settings.DEPLOYMENT_MODE == "saas":
    urlpatterns += [
        path(f"api/{WISDOM_API_VERSION}/wca/", include("ansible_ai_connect.ai.api.wca.urls")),
        path("console/", ConsoleView.as_view(), name="console"),
        path("console/<slug:slug1>/", ConsoleView.as_view(), name="console"),
        path("console/<slug:slug1>/<slug:slug2>/", ConsoleView.as_view(), name="console"),
        path(
            f"api/{WISDOM_API_VERSION}/telemetry/",
            TelemetrySettingsView.as_view(),
            name="telemetry_settings",
        ),
    ]

if settings.DEBUG:
    urlpatterns += [
        path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
        path(
            "api/schema/swagger-ui/",
            SpectacularSwaggerView.as_view(url_name="schema"),
            name="swagger-ui",
        ),
        path(
            "api/schema/redoc/",
            SpectacularRedocView.as_view(url_name="schema"),
            name="redoc",
        ),
    ]
