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

from functools import wraps

from django.contrib.auth.models import AnonymousUser
from django.views.decorators.cache import cache_page


def cache_per_user(timeout):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            user = request.user
            if isinstance(user, AnonymousUser):
                return view_func(request, *args, **kwargs)

            user_uuid = request.user.uuid
            return cache_page(timeout, key_prefix=f"_user_{user_uuid}_")(view_func)(
                request, *args, **kwargs
            )

        return wrapped_view

    return decorator
