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

# NOTE: require the sso.stage credentials
import os
from datetime import datetime, timedelta

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
my_token.server = "sso.stage.redhat.com"


def check(user_id, org_id) -> bool:
    r = requests.post(
        "https://ciam-authz-hw-ciam-authz--runtime-ext.apps.ext.spoke.preprod.us-east-1.aws.paas.redhat.com/v1alpha/check",  # noqa: E501
        json={
            "subject": str(user_id),
            "operation": "access",
            "resourcetype": "license",
            "resourceid": f"{org_id}/smarts",
        },
        headers={
            "Authorization": f"Bearer {my_token.get()}",
        },
    )
    data = r.json()
    return data["result"]


assert check("55903359", "16789634") is True  # goneri56
assert check("55904389", "16789634") is False  # sarahnoseat
print("Success")
