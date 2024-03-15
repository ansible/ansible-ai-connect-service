#!/usr/bin/env python3
# NOTE: require the sso.stage credentials

import os
from datetime import datetime, timedelta
from http import HTTPStatus
from urllib.parse import urlsplit, urlunsplit
from urllib.error import URLError

import re

import requests

AUTHZ_SSO_PATTERN = r"^sso.(.+\.)?redhat.com$"
AUTHZ_API_PATTERN = r"^api.(.+\.)?openshift.com$"


class AuthzURLError(URLError):
    pass


class Token:
    def __init__(self, client_id, client_secret) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self.expiration_date = datetime.fromtimestamp(0)
        self.access_token: str = ""

    def refresh(self) -> None:
        data = {
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "scope": "api.iam.access",
        }

        url = urlsplit(os.environ['AUTHZ_SSO_SERVER'])
        url = parsed_url._replace(path="/auth/realms/redhat-external/protocol/openid-connect/token")

        if not re.search(AUTHZ_SSO_PATTERN, url.netloc):
            raise AuthzURLError(f"Authz URL host ('{url.netloc}') must match '{AUTHZ_SSO_PATTERN}'")

        if url.scheme != "https":
            raise AuthzURLError(f"Authz URL scheme ('{url.scheme}') must be 'https'")

        r = requests.post(
            urlunsplit(url),
            data=data,
        )

        data = r.json()
        self.access_token = data["access_token"]
        expires_in = data["expires_in"]
        self.expiration_date = datetime.utcnow() + timedelta(seconds=expires_in)

    def get(self) -> str:
        if self.expiration_date - datetime.utcnow() < timedelta(seconds=10):
            self.refresh()
        return self.access_token


my_token = Token(os.environ["AUTHZ_SSO_CLIENT_ID"], os.environ["AUTHZ_SSO_CLIENT_SECRET"])


def get_ams_org(rh_org_id: str) -> str:
    params = {"search": f"external_id='{rh_org_id}'"}

    url = urlsplit(os.environ['AUTHZ_API_SERVER'])
    url = url._replace(path="/api/accounts_mgmt/v1/organizations")

    if not re.search(AUTHZ_API_PATTERN, url.netloc):
        raise AuthzURLError(f"Authz URL host ('{url.netloc}') must match '{AUTHZ_API_PATTERN}'")

    if url.scheme != "https":
        raise AuthzURLError(f"Authz URL scheme ('{url.scheme}') must be 'https'")

    r = requests.get(
        urlunsplit(url),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {my_token.get()}",
        },
        params=params,
    )
    items = r.json().get("items")
    return items[0]["id"]


def check(username: str, organization_id: str) -> bool:
    ams_org_id = get_ams_org(organization_id)
    params = {
        "search": "plan.id = 'AnsibleWisdom' AND status = 'Active' AND "
        f"creator.username = '{username}' AND organization_id='{ams_org_id}'"
    }

    r = requests.get(
        "https://api.openshift.com/api/accounts_mgmt/v1/subscriptions",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {my_token.get()}",
        },
        params=params,
    )

    items = r.json().get("items")
    return len(items) > 0


def rh_user_is_org_admin(username: str, organization_id: str) -> bool:
    ams_org_id = get_ams_org(organization_id)
    params = {"search": f"account.username = '{username}' AND organization.id='{ams_org_id}'"}
    r = requests.get(
        "https://api.openshift.com/api/accounts_mgmt/v1/role_bindings",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {my_token.get()}",
        },
        params=params,
    )

    if r.status_code != HTTPStatus.OK:
        print(r.json())
        return False

    result = r.json()
    for item in result['items']:
        if item['role']['id'] == "OrganizationAdmin":
            return True

    return False


assert os.environ["AUTHZ_BACKEND_TYPE"] == "ams"
assert check("ansiblewisdomtesting1", "17233726") is True
assert rh_user_is_org_admin("ansiblewisdomtesting1", "17233726") is True
print("Success")
