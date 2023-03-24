from django.urls import path

from .views import Attributions, Completions, Feedback
from .views import Completions, Feedback

WISDOM_API_VERSION = "v0"
app_name = "wisdom_api"

urlpatterns = [
    path('attributions/', Attributions.as_view(), name='attributions'),
    path(f'{WISDOM_API_VERSION}/ai/completions/', Completions.as_view(), name='completions'),
    path(f'{WISDOM_API_VERSION}/ai/feedback/', Feedback.as_view(), name='feedback'),
]
