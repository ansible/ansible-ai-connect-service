#!/usr/bin/env python3

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

import logging
import sys
from abc import abstractmethod
from datetime import datetime, timedelta
from http import HTTPStatus

import backoff
import requests
from django.conf import settings
from django.core.cache import cache
from django_prometheus.conf import NAMESPACE
from prometheus_client import Counter, Histogram
from requests.exceptions import HTTPError

logger = logging.getLogger(__name__)

# from django_prometheus.middleware.DEFAULT_LATENCY_BUCKETS
DEFAULT_LATENCY_BUCKETS = (
    0.01,
    0.025,
    0.05,
    0.075,
    0.1,
    0.25,
    0.5,
    0.75,
    1.0,
    2.5,
    5.0,
    7.5,
    10.0,
    25.0,
    50.0,
    75.0,
    float("inf"),
)

authz_token_service_hist = Histogram(
    "authz_token_latency_seconds",
    "Histogram of Authz Token API processing time",
    namespace=NAMESPACE,
    buckets=DEFAULT_LATENCY_BUCKETS,
)

authz_ams_get_organization_hist = Histogram(
    "authz_ams_get_organization_latency_seconds",
    "Histogram of Authz AMS get organization API processing time",
    namespace=NAMESPACE,
    buckets=DEFAULT_LATENCY_BUCKETS,
)

authz_ams_get_organization_quota_cost_hist = Histogram(
    "authz_ams_get_organization_quota_cost_latency_seconds",
    "Histogram of Authz AMS get organization quota_cost API processing time",
    namespace=NAMESPACE,
    buckets=DEFAULT_LATENCY_BUCKETS,
)

authz_ams_get_metrics_hist = Histogram(
    "authz_ams_get_metrics_latency_seconds",
    "Histogram of Authz AMS get metrics API processing time",
    namespace=NAMESPACE,
    buckets=DEFAULT_LATENCY_BUCKETS,
)

authz_token_service_retry_counter = Counter(
    "authz_sso_token_service_retries",
    "Counter of Red Hat SSO token service retries",
    namespace=NAMESPACE,
)

authz_ams_service_retry_counter = Counter(
    "authz_ams_service_retries",
    "Counter of AMS service retries",
    namespace=NAMESPACE,
)

authz_ams_org_cache_hit_counter = Counter(
    "authz_ams_org_cache_hits",
    "Counter of the number of times the AMS 'ams_org' cache is hit.",
    namespace=NAMESPACE,
)

authz_ams_rh_org_has_subscription_cache_hit_counter = Counter(
    "authz_ams_rh_org_has_subscription_cache_hits",
    "Counter of the number of times the AMS 'rh_org_has_subscription' cache is hit.",
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


def log_backoff_exception(details):
    _, exc, _ = sys.exc_info()
    logger.info(str(exc))
    logger.info(
        f"Caught retryable error after {details['tries']} tries. "
        f"Waiting {details['wait']} more seconds then retrying..."
    )


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
    def on_backoff(details):
        log_backoff_exception(details)
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
                giveup=fatal_exception,
                on_backoff=self.on_backoff,
            )
            @authz_token_service_hist.time()
            def post_request():
                return requests.post(
                    f"{self._server}/auth/realms/redhat-external/protocol/openid-connect/token",
                    data=data,
                    timeout=self.timeout,
                )

            r = post_request()
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            logger.exception("Cannot reach the SSO backend in time.")
            return None
        except HTTPError:
            logger.exception("SSO token service failed.")
            return None
        if r.status_code != HTTPStatus.OK:
            logger.error(f"Unexpected error code ({r.status_code}) returned by SSO service.")
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


class AMSCheck(BaseCheck):
    # An AMS Organization ID that should never match anything
    ERROR_AMS_ORG_UNDEFINED = "__undefined__"
    ERROR_AMS_CONNECTION_TIMEOUT = "Cannot reach the AMS backend in time."

    class AMSError(Exception):
        pass

    def __init__(self, client_id, client_secret, sso_server, api_server):
        self._session = requests.Session()
        self._token = Token(client_id, client_secret, sso_server)
        self._api_server = api_server
        self._ams_org_cache = {}
        self.retries = settings.AUTHZ_AMS_SERVICE_RETRY_COUNT
        self.timeout = settings.AUTHZ_AMS_SERVICE_TIMEOUT

        if self._api_server.startswith("https://api.stage.openshift.com"):
            proxy = {"https": "http://squid.corp.redhat.com:3128"}
            self._session.proxies.update(proxy)

    @staticmethod
    def on_backoff(details):
        log_backoff_exception(details)
        authz_ams_service_retry_counter.inc()

    def update_bearer_token(self):
        self._session.headers.update({"Authorization": f"Bearer {self._token.get()}"})

    def get_ams_org(self, rh_org_id: int) -> str:
        if not rh_org_id:
            logger.error(f"Unexpected value for rh_org_id: {rh_org_id}.")
            return AMSCheck.ERROR_AMS_ORG_UNDEFINED

        # Check cache
        cache_key = f"rh_org_{rh_org_id}"
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            authz_ams_org_cache_hit_counter.inc(exemplar={"organization_id": str(rh_org_id)})
            return cached_result

        params = {"search": f"external_id='{rh_org_id}'"}
        self.update_bearer_token()

        try:

            @backoff.on_exception(
                backoff.expo,
                Exception,
                max_tries=self.retries + 1,
                giveup=fatal_exception,
                on_backoff=self.on_backoff,
            )
            @authz_ams_get_organization_hist.time()
            def get_request():
                return self._session.get(
                    self._api_server + "/api/accounts_mgmt/v1/organizations",
                    params=params,
                    timeout=self.timeout,
                )

            r = get_request()
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            logger.error(self.ERROR_AMS_CONNECTION_TIMEOUT + f" rh_org_id: {rh_org_id}.")
            raise AMSCheck.AMSError()

        if r.status_code != HTTPStatus.OK:
            logger.error(
                f"Unexpected error code ({r.status_code}) returned by AMS backend (organizations). "
                f"rh_org_id: {rh_org_id}."
            )
            raise AMSCheck.AMSError()

        data = r.json()

        try:
            if len(data["items"]) == 0:
                logger.info(f"An AMS Organization could not be found. " f"rh_org_id: {rh_org_id}.")
                return AMSCheck.ERROR_AMS_ORG_UNDEFINED

            result = data["items"][0]["id"]
            cache.set(cache_key, result, settings.AMS_ORG_CACHE_TIMEOUT_SEC)
            return result
        except (IndexError, KeyError, ValueError):
            logger.exception(
                f"Unexpected answer from AMS backend (organizations). "
                f"rh_org_id: {rh_org_id}, data={data}."
            )
            raise AMSCheck.AMSError

    def self_test(self):
        self.update_bearer_token()

        @authz_ams_get_metrics_hist.time()
        def get_request():
            return self._session.get(
                # A _basic_ call that needs no parameters.
                self._api_server + "/api/accounts_mgmt/v1/metrics",
                timeout=self.timeout,
            )

        r = get_request()
        r.raise_for_status()

    def rh_user_is_org_admin(self, username: str, organization_id: int):
        try:
            ams_org_id = self.get_ams_org(organization_id)
        except AMSCheck.AMSError:
            # See https://issues.redhat.com/browse/AAP-22758
            # If the AMS Organisation lookup fails assume the User is not an administrator
            return False

        if ams_org_id == AMSCheck.ERROR_AMS_ORG_UNDEFINED:
            # Organization has not yet been created in AMS, either the organization
            # is too recent (sync is done every 1h), or the organization has no AMS related
            # services (e.g Ansible, OpenShift, cloud.r.c) and so is not synchronized.
            logger.warning(f"Organization unavailable in AMS, organization_id={organization_id}")
            return False

        params = {"search": f"account.username = '{username}' AND organization.id='{ams_org_id}'"}
        self.update_bearer_token()

        try:
            r = self._session.get(
                self._api_server + "/api/accounts_mgmt/v1/role_bindings",
                params=params,
                timeout=self.timeout,
            )
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            logger.error(self.ERROR_AMS_CONNECTION_TIMEOUT + f" ams_org_id: {ams_org_id}.")
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
                if item["role"]["id"] == "OrganizationAdmin":
                    return True
        except (KeyError, ValueError):
            return False

        return False

    def rh_org_has_subscription(self, organization_id: int) -> bool:
        try:
            ams_org_id = self.get_ams_org(organization_id)
        except AMSCheck.AMSError:
            # See https://issues.redhat.com/browse/AAP-22758
            # If the AMS Organisation lookup fails assume the User has a subscription
            return True

        if ams_org_id == AMSCheck.ERROR_AMS_ORG_UNDEFINED:
            # Organization has not yet been created in AMS, either the organization
            # is too recent (sync is done every 1h), or the organization has no AMS related
            # services (e.g Ansible, OpenShift, cloud.r.c) and so is not synchronized.
            logger.warning(f"Organization unavailable in AMS, organization_id={organization_id}")
            return False

        # Check cache
        cache_key = f"ams_rh_org_has_subscription_{organization_id}"
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            authz_ams_rh_org_has_subscription_cache_hit_counter.inc(
                exemplar={"organization_id": str(organization_id)}
            )
            return cached_result

        params = {"search": "quota_id LIKE 'seat|ansible.wisdom%'"}
        self.update_bearer_token()

        try:

            @backoff.on_exception(
                backoff.expo,
                Exception,
                max_tries=self.retries + 1,
                giveup=fatal_exception,
                on_backoff=self.on_backoff,
            )
            @authz_ams_get_organization_quota_cost_hist.time()
            def get_request():
                return self._session.get(
                    (
                        f"{self._api_server}"
                        f"/api/accounts_mgmt/v1/organizations/{ams_org_id}/quota_cost"
                    ),
                    params=params,
                    timeout=2.0,
                )

            r = get_request()
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            logger.error(self.ERROR_AMS_CONNECTION_TIMEOUT + f" ams_org_id: {ams_org_id}.")
            return False
        if r.status_code != HTTPStatus.OK:
            logger.error(
                f"Unexpected error code ({r.status_code}) returned by AMS backend (quota_cost). "
                f"organization_id: {organization_id}, ams_org_id: {ams_org_id}."
            )
            return False
        data = r.json()
        try:
            result = data["total"] > 0
            cache.set(cache_key, result, settings.AMS_SUBSCRIPTION_CACHE_TIMEOUT_SEC)
            return result

        except (KeyError, ValueError):
            logger.error(
                f"Unexpected answer from AMS backend (quota_cost). "
                f"organization_id {organization_id}, ams_org_id: {ams_org_id}."
            )
            return False


class DummyCheck(BaseCheck):
    def __init__(self, *kargs):
        # Zero parameter constructor
        pass

    def self_test(self):
        # Always passes. No exception raised.
        pass

    def rh_org_has_subscription(self, organization_id: int) -> bool:
        if settings.AUTHZ_DUMMY_ORGS_WITH_SUBSCRIPTION == "*":
            return True
        orgs_with_subscription = [
            int(i) for i in settings.AUTHZ_DUMMY_ORGS_WITH_SUBSCRIPTION.split(",") if i
        ]
        return organization_id in orgs_with_subscription
