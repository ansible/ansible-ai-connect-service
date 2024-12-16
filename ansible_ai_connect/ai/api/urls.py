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

from .views import (
    Chat,
    Completions,
    ContentMatches,
    Explanation,
    Feedback,
    GenerationPlaybook,
    GenerationRole,
)

urlpatterns = [
    path("completions/", Completions.as_view(), name="completions"),
    path("contentmatches/", ContentMatches.as_view(), name="contentmatches"),
    path("explanations/", Explanation.as_view(), name="explanations"),
    # Legacy
    path("generations/", GenerationPlaybook.as_view(), name="generations"),
    path("generations/playbook", GenerationPlaybook.as_view(), name="generations/playbook"),
    path("generations/role", GenerationRole.as_view(), name="generations/role"),
    path("feedback/", Feedback.as_view(), name="feedback"),
    path("chat/", Chat.as_view(), name="chat"),
]
