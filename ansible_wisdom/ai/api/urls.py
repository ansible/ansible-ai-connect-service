from ai.api.views import Completions
from django.urls import path

from .views import AIModelList

urlpatterns = [
    path('ai/completions/', Completions.as_view(), name='ai-completions'),
    path('ai/models/', AIModelList.as_view(), name='ai-models'),
]
