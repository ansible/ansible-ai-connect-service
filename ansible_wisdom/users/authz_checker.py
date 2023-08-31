#!/usr/bin/env python3
import logging
from datetime import datetime, timedelta
from functools import cache
from http import HTTPStatus

import requests

logger = logging.getLogger(__name__)


class Token:
    def __init__(self, client_id, client_secret, server="sso.redhat.com") -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._server = server
        self.expiration_date = datetime.fromtimestamp(0)
        self.access_token: str = ""

    def refresh(self) -> None:
        data = {
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "scope": "api.iam.access",
        }
        try:
            r = requests.post(
                f"{self._server}/auth/realms/redhat-external/protocol/openid-connect/token",
                data=data,
                timeout=0.8,
            )
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            logger.error("Cannot reach the SSO backend in time")
            return None
        if r.status_code != HTTPStatus.OK:
            logger.error("Unexpected error code returned by SSO service")
            return None
        data = r.json()
        self.access_token = data["access_token"]
        expires_in = data["expires_in"]
        self.expiration_date = datetime.utcnow() + timedelta(seconds=expires_in)

    def get(self) -> str:
        if self.expiration_date - datetime.utcnow() < timedelta(seconds=3):
            self.refresh()
        return self.access_token


class CIAMCheck:
    def __init__(self, client_id, client_secret, sso_server, api_server):
        self._session = requests.Session()
        self._token = Token(client_id, client_secret, sso_server)
        self._api_server = api_server

    def check(self, user_id, _username, org_id) -> bool:
        self._session.headers.update({"Authorization": f"Bearer {self._token.get()}"})
        try:
            r = self._session.post(
                self._api_server + "/v1alpha/check",
                json={
                    "subject": str(user_id),
                    "operation": "access",
                    "resourcetype": "license",
                    "resourceid": f"{org_id}/smarts",
                },
                # Note: A ping from France against the preprod env, is slightly below 300ms
                timeout=0.8,
            )
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            logger.error("Cannot reach the CIAM backend in time")
            return False
        if r.status_code != HTTPStatus.OK:
            logger.error("Unexpected error code returned by CIAM backend")
            return False
        data = r.json()
        try:
            return data["result"]
        except (KeyError, TypeError):
            logger.error("Unexpected Answer from CIAM")
            return False


class AMSCheck:
    ERROR_AMS_CONNECTION_TIMEOUT = "Cannot reach the AMS backend in time"

    def __init__(self, client_id, client_secret, sso_server, api_server):
        self._session = requests.Session()
        self._token = Token(client_id, client_secret, sso_server)
        self._api_server = api_server
        self._ams_org_cache = {}

        if self._api_server.startswith("https://api.stage.openshift.com"):
            proxy = {"https": "http://squid.corp.redhat.com:3128"}
            self._session.proxies.update(proxy)

    @cache
    def get_ams_org(self, rh_org_id: str) -> str:
        self._session.headers.update({"Authorization": f"Bearer {self._token.get()}"})
        params = {"search": f"external_id='{rh_org_id}'"}

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
            logger.error("Unexpected error code returned by AMS backend (org)")
            return ""
        data = r.json()

        try:
            return data["items"][0]["id"]
        except (KeyError, ValueError):
            logger.error("Unexpected organization answer from AMS")
            return ""

    def check(self, _user_id: str, username: str, organization_id: str) -> bool:
        ams_org_id = self.get_ams_org(organization_id)
        params = {
            "search": "plan.id = 'AnsibleWisdom' AND status = 'Active' AND "
            f"creator.username = '{username}' AND organization_id='{ams_org_id}'"
        }
        self._session.headers.update({"Authorization": f"Bearer {self._token.get()}"})

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
            logger.error("Unexpected error code returned by AMS backend (sub)")
            return ""
        data = r.json()
        try:
            return len(data["items"]) == 1
        except (KeyError, ValueError):
            logger.error("Unexpected subscription answer from AMS")
            return False

    def is_org_admin(self, username: str, organization_id: str):
        ams_org_id = self.get_ams_org(organization_id)
        params = {"search": f"account.username = '{username}' AND organization.id='{ams_org_id}'"}
        self._session.headers.update({"Authorization": f"Bearer {self._token.get()}"})

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
            logger.error("Unexpected error code returned by AMS backend when listing role bindings")
            return False

        result = r.json()
        try:
            for item in result["items"]:
                if item['role']['id'] == "OrganizationAdmin":
                    return True
        except (KeyError, ValueError):
            return False

        return False


class MockAlwaysTrueCheck:
    def __init__(self, *kargs):
        pass

    def check(self, _user_id: str, _username: str, _organization_id: str) -> bool:
        return True

    def is_org_admin(self, username: str, organization_id: str):
        return True


class MockAlwaysFalseCheck:
    def __init__(self, *kargs):
        pass

    def check(self, _user_id: str, _username: str, _organization_id: str) -> bool:
        return False

    def is_org_admin(self, username: str, organization_id: str):
        return False
