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

import datetime

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.utils.timezone import now
from oauth2_provider.models import AccessToken
from oauthlib.common import generate_token

from ansible_ai_connect.organizations.models import ExternalOrganization


class Command(BaseCommand):
    help = "Create an accesstoken for API access (e.g: to run the tests)"

    def add_arguments(self, parser):
        parser.add_argument("--username", type=str, help="User associated with the token")
        parser.add_argument("--password", type=str, help="User password when creating a new user")
        parser.add_argument("--organization-id", type=str, help="Org id of the user")
        parser.add_argument(
            "--token-name", type=str, help="Name of the token", default=generate_token()
        )
        parser.add_argument(
            "--create-user", action="store_true", help="Also create the user.", default=False
        )
        parser.add_argument(
            "--groups", type=str, nargs="*", help="Names of the groups to assign the user to"
        )
        parser.add_argument(
            "--duration", type=int, help="How long the token is valid (minute)", default=60
        )

    def handle(
        self,
        username,
        password,
        organization_id,
        token_name,
        duration,
        create_user,
        groups,
        *args,
        **options,
    ):
        u = None
        if not token_name:
            raise CommandError("token_name cannot be empty")
        if not username:
            username = f"token_{token_name}"

        User = get_user_model()
        u = User.objects.filter(username=username).first()
        if u is None:
            if create_user:
                self.stdout.write(f"Creating a new user {username}")
                n = now()
                u = User.objects.create_user(
                    username=username,
                    password=password,
                    external_username=username,
                    community_terms_accepted=n,
                    commercial_terms_accepted=n,
                )
                if organization_id:
                    u.organization = ExternalOrganization.objects.get_or_create(id=organization_id)[
                        0
                    ]
                    u.save()
            else:
                raise CommandError(f"Cannot find user {username}")

        group_objs = []
        for g in groups or ():
            group_obj, created = Group.objects.get_or_create(name=g)
            group_objs.append(group_obj)

        if group_objs:
            u.groups.add(*(set(group_objs) - set(u.groups.values_list("name", flat=True))))

        if AccessToken.objects.filter(token=token_name).exists():
            self.stdout.write(f"Token {token_name} already exists")
            return

        self.stdout.write(f"Creating a new token called {token_name}")
        AccessToken.objects.create(
            token=token_name,
            user=u,
            scope="read write",
            expires=now() + datetime.timedelta(minutes=duration),
        )
