from functools import wraps

from django.views.decorators.cache import cache_page


def cache_per_user(timeout):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            username = 'unknown'
            if request.user.is_authenticated:
                username = request.user.username

            return cache_page(timeout, key_prefix=f"_user_{username}_")(view_func)(
                request, *args, **kwargs
            )

        return wrapped_view

    return decorator
