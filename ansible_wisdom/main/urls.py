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
from django.contrib.auth import views as auth_views
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from healthcheck.views import WisdomServiceHealthView, WisdomServiceLivenessProbeView
from users.views import CurrentUserView, HomeView, TermsOfService, UnauthorizedView

WISDOM_API_VERSION = "v0"

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    # add the GitHub OAuth redirect URL /complete/github-team/
    path('', include('social_django.urls', namespace='social')),
    path('', include('django_prometheus.urls')),
    path('admin/', admin.site.urls),
    path(f'api/{WISDOM_API_VERSION}/ai/', include("ai.api.urls")),
    path(f'api/{WISDOM_API_VERSION}/me/', CurrentUserView.as_view(), name='me'),
    path('unauthorized/', UnauthorizedView.as_view(), name='unauthorized'),
    path('check/status/', WisdomServiceHealthView.as_view(), name='health_check'),
    path('check/', WisdomServiceLivenessProbeView.as_view(), name='liveness_probe'),
    path('terms_of_service/', TermsOfService.as_view(), name='terms_of_service'),
    path('o/', include('oauth2_provider.urls', namespace='oauth2_provider')),
    path(
        'login/',
        auth_views.LoginView.as_view(
            extra_context={
                'pilot_contact': settings.PILOT_CONTACT,
                'use_github_team': settings.USE_GITHUB_TEAM,
                'use_redhat_sso': bool(settings.SOCIAL_AUTH_OIDC_OIDC_ENDPOINT),
            }
        ),
        name='login',
    ),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
]

if settings.DEBUG:
    urlpatterns += [
        path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
        path(
            'api/schema/swagger-ui/',
            SpectacularSwaggerView.as_view(url_name='schema'),
            name='swagger-ui',
        ),
        path(
            'api/schema/redoc/',
            SpectacularRedocView.as_view(url_name='schema'),
            name='redoc',
        ),
    ]
