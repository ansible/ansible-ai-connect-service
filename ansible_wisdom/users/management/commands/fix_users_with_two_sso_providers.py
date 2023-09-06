#!/usr/bin/env python3

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from social_django.models import UserSocialAuth

User = get_user_model()


class Command(BaseCommand):
    help = "Ensure no user has 2 different SSO providers"

    def add_arguments(self, parser):
        parser.add_argument("--fix", action="store_true", help="Modify the DB")

    def handle(self, fix, *args, **options):
        cpt = 0
        if not fix:
            self.stdout.write("NOTE: Won't change the DB unless --fix is passed as a parameter")
        for u in User.objects.all():
            # order_by to get the oidc entry first
            usa_entries = UserSocialAuth.objects.all().order_by("-provider").filter(user=u)
            count = usa_entries.count()
            if count < 2:
                continue
            self.stdout.write(f"user={u.username}")
            for e in usa_entries[1:]:
                self.stdout.write(f"  provider={e.provider}")
                if fix:
                    e.delete()
                    cpt += 1

        self.stdout.write(f"{cpt} SSO association removed.")
