from ai.api.views import Completions, Feedback
from django.urls import path

urlpatterns = [
    path('ai/completions/', Completions.as_view(), name='completions'),
    path('ai/feedback/', Feedback.as_view(), name='feedback'),
]
