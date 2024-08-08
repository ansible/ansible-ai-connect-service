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
from textwrap import dedent

from django.conf import settings
from rest_framework import serializers


class UserResponseSerializer(serializers.Serializer):
    # Implemented as a vanilla Serializer as ModelSerializer is driven by the Model definition.
    # Field 'org_telemetry_opt_out' is an extension to the CurrentUserView response dependent
    # upon whether the Telemetry Opt In/Out feature has been enabled.
    rh_org_has_subscription = serializers.BooleanField(read_only=True)
    rh_user_has_seat = serializers.BooleanField(read_only=True)
    rh_user_is_org_admin = serializers.BooleanField(required=False)
    external_username = serializers.CharField(required=False)
    username = serializers.CharField(required=True, max_length=150)
    org_telemetry_opt_out = serializers.BooleanField(required=False)


class MarkdownUserResponseSerializer(serializers.Serializer):
    content = serializers.SerializerMethodField()

    def get_content(self, user):
        markdown_value = ""
        # Enrich with Organisational data, if necessary
        if hasattr(user, "rh_org_has_subscription"):
            markdown_value = f"""
            Logged in as: {user.username}
            """

        if settings.ANSIBLE_AI_ENABLE_ONE_CLICK_TRIAL:
            for up in user.userplan_set.all():
                if up.is_active:
                    expired_at = up.expired_at.strftime("%Y-%m-%d")
                    markdown_value = f"""
                    Logged in as: {user.username}<br>
                    Plan: {up.plan.name}<br>
                    Expiration: {expired_at}
                    """
                    break

        host = self.context["request"].get_host()

        if (
            settings.ANSIBLE_AI_ENABLE_ONE_CLICK_TRIAL
            and user.is_authenticated
            and user.is_oidc_user
            and user.rh_org_has_subscription
            and not user.organization.has_api_key
        ):
            markdown_value = f"""
                Logged in as: {user.username}<br><br>
                Your account is not configured to use Ansible Lightspeed.
                Start a trial to Ansible Lightspeed with IBM watsonx Code Assistant
                by following the link below.<br><br>
                <a href = "https://{host}/trial/">Start trial</a>
            """

        return dedent(markdown_value).strip()
