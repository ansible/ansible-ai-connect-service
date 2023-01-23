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
from rest_framework import routers
from django.contrib.auth import views as auth_views

from .api import views as main_views
from users import views as user_views
from social_django import urls as social_urls

# router = routers.DefaultRouter()
# router.register(r'users', main_views.UserViewSet)
# router.register(r'groups', main_views.GroupViewSet)

urlpatterns = [
    # path('', include(router.urls)),
    path("admin/", admin.site.urls),

    # add the GitHub OAuth redirect URL /complete/github-team/
    path('', include('social_django.urls', namespace='social')),
        
    path("api/", include("ai.api.urls")),
    
    # Temp Wisdom home page to share token for pilot
    path('', user_views.home, name='home'),
    path('login/', auth_views.LoginView.as_view(extra_context={'pilot_contact': settings.PILOT_CONTACT}), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
]
