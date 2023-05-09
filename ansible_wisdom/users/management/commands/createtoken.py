#!/usr/bin/env python3

import datetime

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.utils.timezone import now
from oauth2_provider.models import AccessToken
from oauthlib.common import generate_token


class Command(BaseCommand):
    help = "Create an accesstoken for API access (e.g: to run the tests)"

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, help="User associated with the token")
        parser.add_argument(
            '--token-name', type=str, help="Name of the token", default=generate_token()
        )
        parser.add_argument(
            '--create-user', action='store_true', help="Also create the user.", default=False
        )
        parser.add_argument(
            '--groups', type=str, nargs='*', help="Names of the groups to assign the user to"
        )
        parser.add_argument(
            '--duration', type=int, help="How long the token is valid (minute)", default=60
        )

    def handle(self, username, token_name, duration, create_user, groups, *args, **options):
        u = None
        if not token_name:
            raise CommandError("token_name cannot be empty")
        if not username:
            username = f"token_{token_name}"

        User = get_user_model()
        if not User.objects.filter(username=username).exists():
            if create_user:
                u = User.objects.create_user(username=username, date_terms_accepted=now())
            else:
                raise CommandError(f"Cannot find user {username}")
        else:
            u = User.objects.get(username=username)

        if not u.date_terms_accepted:
            raise CommandError(
                f"User {username} already exists but the user "
                "didn't accept the terms and conditions"
            )

        group_objs = []
        for g in groups:
            group_obj, created = Group.objects.get_or_create(name=g)
            group_objs.append(group_obj)

        if group_objs:
            u.groups.add(*(set(group_objs) - set(u.groups.values_list('name', flat=True))))

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
