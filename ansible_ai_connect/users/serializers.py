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

from rest_framework import serializers

from ansible_ai_connect.organizations.serializers import OrganizationSerializer
from ansible_ai_connect.users.models import Plan, UserPlan
from ansible_ai_connect.users.one_click_trial import OneClickTrial


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ["id", "name"]


class UserPlanSerializer(serializers.ModelSerializer):
    plan = PlanSerializer()

    class Meta:
        model = UserPlan
        fields = ["created_at", "expired_at", "accept_marketing", "plan"]


class UserResponseSerializer(serializers.Serializer):
    # Implemented as a vanilla Serializer as ModelSerializer is driven by the Model definition.
    # Field 'org_telemetry_opt_out' is an extension to the CurrentUserView response dependent
    # upon whether the Telemetry Opt In/Out feature has been enabled.
    email = serializers.CharField(required=False)
    external_username = serializers.CharField(required=False)
    family_name = serializers.CharField(required=False)
    given_name = serializers.CharField(required=False)
    org_telemetry_opt_out = serializers.BooleanField(required=False)
    organization = OrganizationSerializer(required=False, allow_null=True)
    rh_org_has_subscription = serializers.BooleanField(read_only=True)
    rh_user_has_seat = serializers.BooleanField(read_only=True)
    rh_user_is_org_admin = serializers.BooleanField(required=False)
    username = serializers.CharField(required=True, max_length=150)
    userplan_set = UserPlanSerializer(many=True)
    uuid = serializers.UUIDField(required=True)


class MarkdownUserResponseSerializer(serializers.Serializer):
    content = serializers.SerializerMethodField()

    def get_content(self, user):
        markdown_value = ""
        # Enrich with Organisational data, if necessary
        if hasattr(user, "rh_org_has_subscription"):
            markdown_value = f"""
            Logged in as: {user.username}
            """

        host = self.context["request"].get_host()
        one_click_trial_markdown = OneClickTrial(user).get_markdown(host)

        if one_click_trial_markdown:
            return one_click_trial_markdown

        return dedent(markdown_value).strip()
