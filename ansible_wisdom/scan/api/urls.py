from django.urls import path

from .views import ContentScan

urlpatterns = [
    path('content/', ContentScan.as_view(), name='content'),
]
