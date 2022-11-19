from django.urls import path, include
from rest_framework import routers
from wisdom.main import views

router = routers.DefaultRouter()
router.register(r'users', views.UserViewSet)
router.register(r'groups', views.GroupViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    path('', include('social_django.urls', namespace='social')),  # still need to hook the views up
]
