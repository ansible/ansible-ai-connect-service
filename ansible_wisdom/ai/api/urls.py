from ai.api.views import Completions
from django.urls import path

urlpatterns = [
    path('completions/', Completions.as_view(), name='completions'),
]
