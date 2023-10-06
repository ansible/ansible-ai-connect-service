import logging

from django.core import exceptions as core_exceptions
from django.http import HttpResponseRedirect
from django.views.generic import TemplateView
from rest_framework import exceptions
from rest_framework.request import Request
from rest_framework.settings import api_settings

logger = logging.getLogger(__name__)


class ProtectedTemplateView(TemplateView):
    """
    Extends TemplateView to add support for BasePermission
    re-use that are tied to APIView implementations.

    Much of the implementation has been copied from APIView.
    """

    # The following policies may be set at either globally, or per-view.
    permission_classes = api_settings.DEFAULT_PERMISSION_CLASSES
    authentication_classes = api_settings.DEFAULT_AUTHENTICATION_CLASSES

    # Allow dependency injection of other settings to make testing easier.
    settings = api_settings

    def dispatch(self, request, *args, **kwargs):
        # Wrap Request object to support forced authentication in tests
        request = self.initialize_request(request, *args, **kwargs)

        try:
            self.initial(request, *args, **kwargs)

            # Try to dispatch to the right method; if a method doesn't exist,
            # defer to the error handler. Also defer to the error handler if the
            # request method isn't on the approved list.
            if request.method.lower() in self.http_method_names:
                handler = getattr(self, request.method.lower(), self.http_method_not_allowed)
            else:
                handler = self.http_method_not_allowed

            # This is a TemplateResponse
            return handler(request, *args, **kwargs)

        except exceptions.NotAuthenticated:
            return HttpResponseRedirect("/login")

        except Exception as exc:
            # Map _internal_ errors to a generic PermissionDenied error
            # for which Django handles rendering a default view to Users
            if isinstance(
                exc,
                (
                    exceptions.AuthenticationFailed,
                    exceptions.PermissionDenied,
                ),
            ):
                raise core_exceptions.PermissionDenied()
            else:
                raise exc

    def initialize_request(self, request, *args, **kwargs):
        """
        Returns the initial request object.
        """
        parser_context = {
            'view': self,
            'args': getattr(self, 'args', ()),
            'kwargs': getattr(self, 'kwargs', {}),
        }

        return Request(
            request, authenticators=self.get_authenticators(), parser_context=parser_context
        )

    def get_authenticators(self):
        """
        Instantiates and returns the list of authenticators that this view can use.
        """
        return [ac() for ac in self.authentication_classes]

    def initial(self, request, *args, **kwargs):
        """
        Runs anything that needs to occur prior to calling the method handler.
        """
        # Ensure that the incoming request is permitted
        self.perform_authentication(request)
        self.check_permissions(request)

    @staticmethod
    def perform_authentication(request):
        """
        Perform authentication on the incoming request.

        Note that if you override this and simply 'pass', then authentication
        will instead be performed lazily, the first time either
        `request.user` or `request.auth` is accessed.
        """
        request.user

    def check_permissions(self, request):
        """
        Check if the request should be permitted.
        Raises an appropriate exception if the request is not permitted.
        """

        def get_permissions():
            """
            Instantiates and returns the list of permissions that this view requires.
            """
            return [pc() for pc in self.permission_classes]

        def permission_denied(r, message=None, code=None):
            """
            If request is not permitted, determine what kind of exception to raise.
            """
            if r.authenticators and not r.successful_authenticator:
                raise exceptions.NotAuthenticated()
            raise exceptions.PermissionDenied(detail=message, code=code)

        for permission in get_permissions():
            if not permission.has_permission(request, self):
                permission_denied(
                    request,
                    message=getattr(permission, 'message', None),
                    code=getattr(permission, 'code', None),
                )
