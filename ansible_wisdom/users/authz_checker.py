#!/usr/bin/env python3
import logging
from abc import abstractmethod
from datetime import datetime, timedelta
from http import HTTPStatus

import backoff
import requests
from django.conf import settings
from django.core.cache import cache
from django_prometheus.conf import NAMESPACE
from prometheus_client import Counter
from requests.exceptions import HTTPError

logger = logging.getLogger(__name__)

authz_token_service_retry_counter = Counter(
    'authz_sso_token_service_retries',
    "Counter of Red Hat SSO token service retries",
    namespace=NAMESPACE,
)


class BaseCheck:
    @abstractmethod
    def self_test(self):
        """
        Check the health of the underlying authentication service.
        Any exception signifies a failure of the underlying service.
        """
        pass

    @abstractmethod
    def check(self, _user_id: str, username: str, organization_id: int) -> bool:
        pass


class Token:
    def __init__(self, client_id, client_secret, server="sso.redhat.com") -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._server = server
        self.expiration_date = datetime.fromtimestamp(0)
        self.access_token: str = ""
        self.retries = settings.AUTHZ_SSO_TOKEN_SERVICE_RETRY_COUNT
        self.timeout = settings.AUTHZ_SSO_TOKEN_SERVICE_TIMEOUT

    @staticmethod
    def fatal_exception(exc) -> bool:
        """Determine if an exception is fatal or not"""
        if isinstance(exc, requests.RequestException):
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            # retry on server errors and client errors
            # with 429 status code (rate limited),
            # don't retry on other client errors
            return bool(status_code and (400 <= status_code < 500) and status_code != 429)
        else:
            # retry on all other errors (e.g. network)
            return False

    @staticmethod
    def on_backoff(details):
        authz_token_service_retry_counter.inc()

    def refresh(self) -> None:
        data = {
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "scope": "api.iam.access",
        }
        try:

            @backoff.on_exception(
                backoff.expo,
                Exception,
                max_tries=self.retries + 1,
                giveup=self.fatal_exception,
                on_backoff=self.on_backoff,
            )
            def post_request():
                return requests.post(
                    f"{self._server}/auth/realms/redhat-external/protocol/openid-connect/token",
                    data=data,
                    timeout=self.timeout,
                )

            r = post_request()
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            logger.exception("Cannot reach the SSO backend in time")
            return None
        except HTTPError:
            logger.exception("SSO token service failed")
            return None
        if r.status_code != HTTPStatus.OK:
            logger.error("Unexpected error code (%s) returned by SSO service" % r.status_code)
            return None
        data = r.json()
        self.access_token = data["access_token"]
        expires_in = data["expires_in"]
        self.expiration_date = datetime.utcnow() + timedelta(seconds=expires_in)

    def get(self) -> str:
        if self.expiration_date - datetime.utcnow() < timedelta(seconds=3):
            self.refresh()
        return self.access_token


class CIAMCheck(BaseCheck):
    def __init__(self, client_id, client_secret, sso_server, api_server):
        self._session = requests.Session()
        self._token = Token(client_id, client_secret, sso_server)
        self._api_server = api_server

    def self_test(self):
        self._session.headers.update({"Authorization": f"Bearer {self._token.get()}"})
        r = self._session.post(
            self._api_server + "/v1alpha/healthcheck",
            timeout=0.8,
        )
        r.raise_for_status()

    def check(self, user_id, username, organization_id) -> bool:
        self._session.headers.update({"Authorization": f"Bearer {self._token.get()}"})
        try:
            r = self._session.post(
                self._api_server + "/v1alpha/check",
                json={
                    "subject": str(user_id),
                    "operation": "access",
                    "resourcetype": "license",
                    "resourceid": f"{organization_id}/smarts",
                },
                # Note: A ping from France against the preprod env, is slightly below 300ms
                timeout=0.8,
            )
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            logger.error("Cannot reach the CIAM backend in time")
            return False
        if r.status_code != HTTPStatus.OK:
            logger.error("Unexpected error code (%s) returned by CIAM backend" % r.status_code)
            return False
        data = r.json()
        try:
            return data["result"]
        except (KeyError, TypeError):
            logger.error("Unexpected Answer from CIAM")
            return False


class AMSCheck(BaseCheck):
    ERROR_AMS_CONNECTION_TIMEOUT = "Cannot reach the AMS backend in time"

    def __init__(self, client_id, client_secret, sso_server, api_server):
        self._session = requests.Session()
        self._token = Token(client_id, client_secret, sso_server)
        self._api_server = api_server
        self._ams_org_cache = {}

        if self._api_server.startswith("https://api.stage.openshift.com"):
            proxy = {"https": "http://squid.corp.redhat.com:3128"}
            self._session.proxies.update(proxy)

    def update_bearer_token(self):
        self._session.headers.update({"Authorization": f"Bearer {self._token.get()}"})

    def get_ams_org(self, rh_org_id: str) -> str:
        if rh_org_id is None or not bool(str(rh_org_id).strip()):
            logger.error(f"Unexpected value for rh_org_id: {rh_org_id}")
            return ""
        cache_key = f"rh_org_{rh_org_id}"
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return cached_result

        params = {"search": f"external_id='{rh_org_id}'"}
        self.update_bearer_token()

        try:
            r = self._session.get(
                self._api_server + "/api/accounts_mgmt/v1/organizations",
                params=params,
                timeout=0.8,
            )
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            logger.error(self.ERROR_AMS_CONNECTION_TIMEOUT)
            return ""
        if r.status_code != HTTPStatus.OK:
            logger.error("Unexpected error code (%s) returned by AMS backend (org)" % r.status_code)
            return ""
        data = r.json()

        try:
            result = data["items"][0]["id"]
            cache.set(cache_key, result, 60 * 60 * 24)  # cache for one day
            return result
        except (IndexError, KeyError, ValueError):
            logger.exception("Unexpected organization answer from AMS: data=%s" % data)
            return ""

    def self_test(self):
        self.update_bearer_token()
        r = self._session.get(
            # A _basic_ call that needs no parameters.
            self._api_server + "/api/accounts_mgmt/v1/metrics",
            timeout=0.8,
        )
        r.raise_for_status()

    def check(self, user_id: str, username: str, organization_id: int) -> bool:
        ams_org_id = self.get_ams_org(organization_id)
        params = {
            "search": "plan.id = 'AnsibleWisdom' AND status = 'Active' AND "
            f"creator.username = '{username}' AND organization_id='{ams_org_id}'"
        }
        self.update_bearer_token()

        try:
            r = self._session.get(
                self._api_server + "/api/accounts_mgmt/v1/subscriptions",
                params=params,
                timeout=0.8,
            )
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            logger.error(self.ERROR_AMS_CONNECTION_TIMEOUT)
            return False
        if r.status_code != HTTPStatus.OK:
            logger.error("Unexpected error code (%s) returned by AMS backend (sub)" % r.status_code)
            return False
        data = r.json()
        try:
            return len(data["items"]) > 0
        except (KeyError, ValueError):
            logger.error("Unexpected subscription answer from AMS")
            return False

    def rh_user_is_org_admin(self, username: str, organization_id: str):
        ams_org_id = self.get_ams_org(organization_id)
        params = {"search": f"account.username = '{username}' AND organization.id='{ams_org_id}'"}
        self.update_bearer_token()

        try:
            r = self._session.get(
                self._api_server + "/api/accounts_mgmt/v1/role_bindings",
                params=params,
                timeout=0.8,
            )
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            logger.error(self.ERROR_AMS_CONNECTION_TIMEOUT)
            return False

        if r.status_code != HTTPStatus.OK:
            logger.error(
                "Unexpected error code (%s) returned by AMS backend when listing role bindings"
                % r.status_code
            )
            return False

        result = r.json()
        try:
            for item in result["items"]:
                if item['role']['id'] == "OrganizationAdmin":
                    return True
        except (KeyError, ValueError):
            return False

        return False

    def rh_org_has_subscription(self, organization_id: str) -> bool:
        ams_org_id = self.get_ams_org(organization_id)
        params = {"search": "quota_id LIKE 'seat|ansible.wisdom%'"}
        self.update_bearer_token()

        try:
            r = self._session.get(
                (
                    f"{self._api_server}"
                    f"/api/accounts_mgmt/v1/organizations/{ams_org_id}/quota_cost"
                ),
                params=params,
                timeout=0.8,
            )
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            logger.error(self.ERROR_AMS_CONNECTION_TIMEOUT)
            return False
        if r.status_code != HTTPStatus.OK:
            logger.error(
                "Unexpected error code (%s) returned by AMS backend when listing resource_quota"
                % r.status_code
            )
            return False
        data = r.json()
        try:
            return data["total"] > 0
        except (KeyError, ValueError):
            logger.error("Unexpected resource_quota answer from AMS")
            return False


class DummyCheck(BaseCheck):
    def __init__(self, *kargs):
        # Zero parameter constructor
        pass

    def self_test(self):
        # Always passes. No exception raised.
        pass

    def check(self, _user_id: str, username: str, organization_id: int) -> bool:
        if not self.rh_org_has_subscription(organization_id):
            return False
        if settings.AUTHZ_DUMMY_USERS_WITH_SEAT == "*":
            return True
        seated_user = settings.AUTHZ_DUMMY_USERS_WITH_SEAT.split(",")
        return username in seated_user

    def rh_org_has_subscription(self, organization_id: int) -> bool:
        if settings.AUTHZ_DUMMY_ORGS_WITH_SUBSCRIPTION == "*":
            return True
        orgs_with_subscription = [
            int(i) for i in settings.AUTHZ_DUMMY_ORGS_WITH_SUBSCRIPTION.split(",") if i
        ]
        return organization_id in orgs_with_subscription
