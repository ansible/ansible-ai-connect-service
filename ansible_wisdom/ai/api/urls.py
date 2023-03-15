from django.urls import path

from .views import Completions, Feedback

urlpatterns = [
    path('completions/', Completions.as_view(), name='completions'),
    path('feedback/', Feedback.as_view(), name='feedback'),
]
