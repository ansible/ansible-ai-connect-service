from django.conf import settings
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from ansible_ai_connect.main.middleware import EnsureCsrfCookieMiddleware
from ansible_ai_connect.main.settings import base as base_settings


class TestBaseCookieSecuritySettings(TestCase):

    def test_session_cookie_secure(self):
        self.assertTrue(base_settings.SESSION_COOKIE_SECURE)

    def test_session_cookie_httponly(self):
        self.assertTrue(base_settings.SESSION_COOKIE_HTTPONLY)

    def test_session_cookie_samesite(self):
        self.assertEqual(base_settings.SESSION_COOKIE_SAMESITE, "Lax")

    def test_session_cookie_name_has_host_prefix(self):
        self.assertEqual(base_settings.SESSION_COOKIE_NAME, "__Host-sessionid")

    def test_session_cookie_age_two_weeks(self):
        self.assertEqual(base_settings.SESSION_COOKIE_AGE, 1209600)

    def test_csrf_cookie_secure(self):
        self.assertTrue(base_settings.CSRF_COOKIE_SECURE)

    def test_csrf_cookie_not_httponly(self):
        self.assertFalse(base_settings.CSRF_COOKIE_HTTPONLY)

    def test_csrf_cookie_samesite(self):
        self.assertEqual(base_settings.CSRF_COOKIE_SAMESITE, "Lax")

    def test_csrf_cookie_name_has_host_prefix(self):
        self.assertEqual(base_settings.CSRF_COOKIE_NAME, "__Host-csrftoken")

    def test_csrf_cookie_age_two_weeks(self):
        self.assertEqual(base_settings.CSRF_COOKIE_AGE, 1209600)

    def test_host_prefix_invariants_session_domain_unset(self):
        self.assertFalse(getattr(base_settings, "SESSION_COOKIE_DOMAIN", None))

    def test_host_prefix_invariants_session_path(self):
        self.assertEqual(getattr(base_settings, "SESSION_COOKIE_PATH", "/"), "/")

    def test_host_prefix_invariants_csrf_domain_unset(self):
        self.assertFalse(getattr(base_settings, "CSRF_COOKIE_DOMAIN", None))

    def test_host_prefix_invariants_csrf_path(self):
        self.assertEqual(getattr(base_settings, "CSRF_COOKIE_PATH", "/"), "/")


class TestEnsureCsrfCookieMiddleware(TestCase):

    def setUp(self):
        self.factory = RequestFactory()

    def test_middleware_in_stack(self):
        self.assertIn(
            "ansible_ai_connect.main.middleware.EnsureCsrfCookieMiddleware",
            settings.MIDDLEWARE,
        )

    def test_middleware_before_csrf_middleware(self):
        idx_ensure = settings.MIDDLEWARE.index(
            "ansible_ai_connect.main.middleware.EnsureCsrfCookieMiddleware"
        )
        idx_csrf = settings.MIDDLEWARE.index("django.middleware.csrf.CsrfViewMiddleware")
        self.assertLess(idx_ensure, idx_csrf)

    def test_sets_csrf_cookie_needs_update(self):
        request = self.factory.get("/")
        middleware = EnsureCsrfCookieMiddleware(get_response=lambda r: HttpResponse())
        middleware(request)
        self.assertTrue(request.META.get("CSRF_COOKIE_NEEDS_UPDATE"))

    def test_sets_csrf_cookie_secret(self):
        request = self.factory.get("/")
        middleware = EnsureCsrfCookieMiddleware(get_response=lambda r: HttpResponse())
        middleware(request)
        self.assertIn("CSRF_COOKIE", request.META)
        self.assertTrue(len(request.META["CSRF_COOKIE"]) > 0)

    def test_reuses_existing_csrf_cookie_secret(self):
        request = self.factory.get("/")
        existing_secret = "ExistingCsrfSecret12345678901234"
        request.COOKIES[settings.CSRF_COOKIE_NAME] = existing_secret
        middleware = EnsureCsrfCookieMiddleware(get_response=lambda r: HttpResponse())
        middleware(request)
        self.assertEqual(request.META["CSRF_COOKIE"], existing_secret)

    def test_does_not_overwrite_existing_csrf_cookie_in_cookies(self):
        request = self.factory.get("/")
        existing_secret = "ExistingCsrfSecret12345678901234"
        request.COOKIES[settings.CSRF_COOKIE_NAME] = existing_secret
        middleware = EnsureCsrfCookieMiddleware(get_response=lambda r: HttpResponse())
        middleware(request)
        self.assertEqual(request.COOKIES[settings.CSRF_COOKIE_NAME], existing_secret)

    def test_uses_header_token_when_cookie_missing(self):
        """When the browser doesn't send the CSRF cookie but JS sends
        X-CSRFToken (cross-origin proxy deployment), use the header
        value as the secret."""
        request = self.factory.get("/", HTTP_X_CSRFTOKEN="HeaderCsrfToken12345678901234567")
        middleware = EnsureCsrfCookieMiddleware(get_response=lambda r: HttpResponse())
        middleware(request)
        self.assertEqual(
            request.META["CSRF_COOKIE"],
            "HeaderCsrfToken12345678901234567",
        )
        self.assertEqual(
            request.COOKIES[settings.CSRF_COOKIE_NAME],
            "HeaderCsrfToken12345678901234567",
        )

    def test_cookie_takes_precedence_over_header(self):
        """When both cookie and header exist, the cookie value is used
        as the CSRF secret (standard double-submit pattern)."""
        request = self.factory.get("/", HTTP_X_CSRFTOKEN="HeaderToken123456789012345678901")
        cookie_secret = "CookieSecret12345678901234567890"
        request.COOKIES[settings.CSRF_COOKIE_NAME] = cookie_secret
        middleware = EnsureCsrfCookieMiddleware(get_response=lambda r: HttpResponse())
        middleware(request)
        self.assertEqual(request.META["CSRF_COOKIE"], cookie_secret)

    def test_uses_form_token_when_cookie_and_header_missing(self):
        """When a form POST has csrfmiddlewaretoken but no cookie
        (OAuth/gateway cross-origin proxy), inject the form token
        into COOKIES so CsrfViewMiddleware can validate it."""
        form_token = "a" * 64
        request = self.factory.post("/logout/", {"csrfmiddlewaretoken": form_token})
        middleware = EnsureCsrfCookieMiddleware(get_response=lambda r: HttpResponse())
        middleware(request)
        self.assertEqual(request.COOKIES[settings.CSRF_COOKIE_NAME], form_token)
        self.assertNotIn("CSRF_COOKIE", request.META)

    def test_form_token_not_used_when_cookie_exists(self):
        """When the cookie exists, the form token is ignored and the
        cookie value is used as the CSRF secret."""
        cookie_secret = "CookieSecret12345678901234567890"
        form_token = "b" * 64
        request = self.factory.post("/logout/", {"csrfmiddlewaretoken": form_token})
        request.COOKIES[settings.CSRF_COOKIE_NAME] = cookie_secret
        middleware = EnsureCsrfCookieMiddleware(get_response=lambda r: HttpResponse())
        middleware(request)
        self.assertEqual(request.META["CSRF_COOKIE"], cookie_secret)

    def test_post_without_form_token_generates_fresh_secret(self):
        """POST with no cookie, no header, and no csrfmiddlewaretoken
        falls through to case 4 and generates a fresh secret."""
        request = self.factory.post("/some-endpoint/")
        middleware = EnsureCsrfCookieMiddleware(get_response=lambda r: HttpResponse())
        middleware(request)
        self.assertTrue(request.META.get("CSRF_COOKIE_NEEDS_UPDATE"))
        self.assertIn("CSRF_COOKIE", request.META)
        self.assertTrue(len(request.META["CSRF_COOKIE"]) > 0)
        self.assertIn(settings.CSRF_COOKIE_NAME, request.COOKIES)


class TestDevelopmentCookieOverrides(TestCase):
    """Development settings relax cookie security for HTTP dev environments
    (__Host- prefix requires Secure, which breaks plain HTTP)."""

    def test_session_cookie_not_secure_in_dev(self):
        from ansible_ai_connect.main.settings import development

        self.assertFalse(development.SESSION_COOKIE_SECURE)

    def test_session_cookie_name_standard_in_dev(self):
        from ansible_ai_connect.main.settings import development

        self.assertEqual(development.SESSION_COOKIE_NAME, "sessionid")

    def test_csrf_cookie_not_secure_in_dev(self):
        from ansible_ai_connect.main.settings import development

        self.assertFalse(development.CSRF_COOKIE_SECURE)

    def test_csrf_cookie_name_standard_in_dev(self):
        from ansible_ai_connect.main.settings import development

        self.assertEqual(development.CSRF_COOKIE_NAME, "csrftoken")


class TestGatewaySettings(TestCase):

    def test_gateway_session_cookie_name_default(self):
        self.assertEqual(base_settings.GATEWAY_SESSION_COOKIE_NAME, "gateway_sessionid")

    def test_gateway_csrf_cookie_name_default(self):
        self.assertEqual(base_settings.GATEWAY_CSRF_COOKIE_NAME, "csrftoken")


class TestEnsureCsrfCookieMiddlewareGateway(TestCase):

    def setUp(self):
        self.factory = RequestFactory()

    def test_aliases_gateway_csrf_cookie_when_behind_gateway(self):
        request = self.factory.get("/")
        request.COOKIES["gateway_sessionid"] = "gw_session"
        request.COOKIES["csrftoken"] = "gwCsrfToken1234567890abcdefABCDE"
        middleware = EnsureCsrfCookieMiddleware(get_response=lambda r: HttpResponse())
        middleware(request)
        self.assertEqual(
            request.COOKIES[settings.CSRF_COOKIE_NAME], "gwCsrfToken1234567890abcdefABCDE"
        )

    def test_does_not_set_csrf_cookie_needs_update_behind_gateway(self):
        request = self.factory.get("/")
        request.COOKIES["gateway_sessionid"] = "gw_session"
        request.COOKIES["csrftoken"] = "gwCsrfToken1234567890abcdefABCDE"
        middleware = EnsureCsrfCookieMiddleware(get_response=lambda r: HttpResponse())
        middleware(request)
        self.assertFalse(request.META.get("CSRF_COOKIE_NEEDS_UPDATE"))

    def test_standalone_when_both_sessions_exist(self):
        request = self.factory.get("/")
        request.COOKIES["gateway_sessionid"] = "gw_session"
        request.COOKIES[settings.SESSION_COOKIE_NAME] = "django_session"
        request.COOKIES["csrftoken"] = "gwCsrfToken1234567890abcdefABCDE"
        middleware = EnsureCsrfCookieMiddleware(get_response=lambda r: HttpResponse())
        middleware(request)
        self.assertTrue(request.META.get("CSRF_COOKIE_NEEDS_UPDATE"))

    def test_falls_back_to_standalone_when_gateway_csrf_cookie_missing(self):
        request = self.factory.get("/")
        request.COOKIES["gateway_sessionid"] = "gw_session"
        middleware = EnsureCsrfCookieMiddleware(get_response=lambda r: HttpResponse())
        middleware(request)
        self.assertTrue(request.META.get("CSRF_COOKIE_NEEDS_UPDATE"))
        self.assertIn("CSRF_COOKIE", request.META)
