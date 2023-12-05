from functools import wraps

from django.views.decorators.cache import cache_page


def cache_per_user(timeout):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            user_uuid = request.user.uuid
            return cache_page(timeout, key_prefix=f"_user_{user_uuid}_")(view_func)(
                request, *args, **kwargs
            )

        return wrapped_view

    return decorator
