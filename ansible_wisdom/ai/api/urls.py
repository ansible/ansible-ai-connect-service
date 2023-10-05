from django.urls import path

from .views import Attributions, Completions, ContentMatches, Feedback

urlpatterns = [
    path('completions/', Completions.as_view(), name='completions'),
    path('feedback/', Feedback.as_view(), name='feedback'),
    path('attributions/', Attributions.as_view(), name='attributions'),
    path('contentmatches/', ContentMatches.as_view(), name='contentmatches'),
]
