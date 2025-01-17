#  Copyright Red Hat
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

from django.urls import path

from . import views

urlpatterns = [
    path("completions/", views.Completions.as_view(), name="completions"),
    path("contentmatches/", views.ContentMatches.as_view(), name="contentmatches"),
    path("explanations/", views.Explanation.as_view(), name="explanations"),
    path("generations/playbook/", views.GenerationPlaybook.as_view(), name="generations/playbook"),
    path("generations/role/", views.GenerationRole.as_view(), name="generations/role"),
    path("feedback/", views.Feedback.as_view(), name="feedback"),
    path("chat/", views.Chat.as_view(), name="chat"),
]
