from django.urls import path
from .views import CurrentUserView

WISDOM_API_VERSION = "v0"


app_name = "wisdom_users"

urlpatterns = [
    path(f'{WISDOM_API_VERSION}/me/', CurrentUserView.as_view(), name='me'),
]
