#!/usr/bin/env python3
# NOTE: require the sso.stage credentials

import os
from datetime import datetime, timedelta
from pprint import pprint

import requests


class Token:
    def __init__(self, client_id, client_secret) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self.expiration_date = datetime.fromtimestamp(0)
        self.access_token: str = ""
        self.server = "sso.redhat.com"

    def refresh(self) -> None:
        data = {
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "scope": "api.iam.access",
        }

        r = requests.post(
            f"https://{self.server}/auth/realms/redhat-external/protocol/openid-connect/token",
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


my_token = Token(os.environ["CLIENT_ID"], os.environ["CLIENT_SECRET"])


def get_ams_org(rh_org_id: str) -> str:
    params = {"search": f"external_id='{rh_org_id}'"}

    r = requests.get(
        "https://api.openshift.com/api/accounts_mgmt/v1/organizations",
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
    return len(items) == 1


assert check("ansiblewisdomtesting1", "17233726") is True
assert check("goneri", "11009103") is False  # Org: 1HAXGgCYqHpednsRDiwWsZBmDlA
assert check("gleboude@redhat.com", "11009103") is False
assert check("gleboude1@redhat.com", "11009103") is False
print("Success")
