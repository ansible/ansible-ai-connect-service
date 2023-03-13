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
from users.views import CurrentUserView, HomeView, UnauthorizedView

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    # add the GitHub OAuth redirect URL /complete/github-team/
    path('', include('social_django.urls', namespace='social')),
    path('admin/', admin.site.urls),
    path('api/', include("ai.api.urls")),
    path('api/me/', CurrentUserView.as_view(), name='me'),
    path('unauthorized/', UnauthorizedView.as_view(), name='unauthorized'),
    # Temp Wisdom home page to share token for pilot
    path(
        'login/',
        auth_views.LoginView.as_view(extra_context={'pilot_contact': settings.PILOT_CONTACT}),
        name='login',
    ),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', include('django_prometheus.urls')),
]

# OAUTH: merge above
if settings.OAUTH2_ENABLE:
    urlpatterns.append(path('o/', include('oauth2_provider.urls', namespace='oauth2_provider')))

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
