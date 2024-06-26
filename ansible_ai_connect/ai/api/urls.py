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

from .views import Completions, Feedback
from .views2 import ContentMatches
from .views3 import Generation
from .views4 import Explanation

urlpatterns = [
    path("completions/", Completions.as_view(), name="completions"),
    path("contentmatches/", ContentMatches.as_view(), name="contentmatches"),
    path("explanations/", Explanation.as_view(), name="explanations"),
    path("generations/", Generation.as_view(), name="generations"),
    path("feedback/", Feedback.as_view(), name="feedback"),
]
