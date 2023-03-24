from django.urls import path

from .views import Attributions, Completions, Feedback

app_name = "wisdom"

urlpatterns = [
    path('completions/', Completions.as_view(), name='completions'),
    path('feedback/', Feedback.as_view(), name='feedback'),
    path('attributions/', Attributions.as_view(), name='attributions'),
]
