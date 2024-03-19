from django.urls import path

from .views import Attributions, Completions, ContentMatches, Explanation, Feedback

urlpatterns = [
    path('attributions/', Attributions.as_view(), name='attributions'),
    path('completions/', Completions.as_view(), name='completions'),
    path('contentmatches/', ContentMatches.as_view(), name='contentmatches'),
    path('explanations/', Explanation.as_view(), name='explanations'),
    path('feedback/', Feedback.as_view(), name='feedback'),
]
