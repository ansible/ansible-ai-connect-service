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

from attr import asdict
from django.conf import settings
from packaging.version import InvalidVersion, Version
from segment.analytics import Client

from ansible_ai_connect.ai.api.utils.segment import (
    base_send_segment_event,
    send_segment_event,
)
from ansible_ai_connect.organizations.models import ExternalOrganization
from ansible_ai_connect.users.models import User

logger = logging.getLogger(__name__)

write_key = Client.DefaultConfig.write_key
host = Client.DefaultConfig.host
on_error = Client.DefaultConfig.on_error
debug = Client.DefaultConfig.debug
send = Client.DefaultConfig.send
sync_mode = Client.DefaultConfig.sync_mode
max_queue_size = Client.DefaultConfig.max_queue_size
gzip = Client.DefaultConfig.gzip
timeout = Client.DefaultConfig.timeout
max_retries = Client.DefaultConfig.max_retries

segment_analytics_client = None


def meets_min_ansible_extension_version(version) -> bool:
    """
    Checks if the extension version, if exists, checks if it satisfies a defined min. version value.
    Requests outside the extension context, such as one-click trial, assume no version parameter.
    """
    if not version:
        return True
    minVersion = Version(settings.ANALYTICS_MIN_ANSIBLE_EXTENSION_VERSION)
    try:
        userVersion = Version(version)
    except InvalidVersion:
        return False
    return userVersion >= minVersion


def send_segment_analytics_event(
    event_enum, event_payload_supplier, user: User, ansibleExtensionVersion=None
):
    if not settings.SEGMENT_ANALYTICS_WRITE_KEY:
        logger.info("Segment analytics write key not set, skipping event.")
        return
    if not user.rh_user_has_seat:
        logger.info("Skipping analytics telemetry event for users that has no seat.")
        return

    if meets_min_ansible_extension_version(ansibleExtensionVersion) is False:
        logger.info(
            f"Skipping analytics telemetry event, extension version: {ansibleExtensionVersion}"
        )
        return

    organization: ExternalOrganization = user.organization
    if not organization:
        logger.info("Analytics telemetry not active, because of no organization assigned for user.")
        return

    if organization.has_telemetry_opt_out:
        logger.info(f"Organization '{organization.id}' has opted out of Analytics telemetry.")
        return

    event_name = event_enum.value
    try:
        payload = event_payload_supplier()
        data_dict = asdict(payload)
        base_send_segment_event(data_dict, event_name, user, get_segment_analytics_client())
    except ValueError as error:
        logger.warning("Error validating analytics event schema: ", error)
        send_segment_analytics_error_event(event_name, error, user)
    except TypeError as error:
        logger.warning("Error converting types in the analytics event schema: ", error)
        send_segment_analytics_error_event(event_name, error, user)


def send_segment_analytics_error_event(event_name: str, ve: Exception, user: User) -> None:
    event = {
        "error_type": "analytics_telemetry_error",
        "details": dict(event_name=event_name, error=ve.__repr__()),
    }
    send_segment_event(event, "analyticsTelemetryError", user)


def get_segment_analytics_client() -> Client:
    """Create an analytics client if one doesn't exist and send to it."""
    global segment_analytics_client
    if not segment_analytics_client:
        segment_analytics_client = Client(
            write_key=write_key,
            host=host,
            debug=debug,
            max_queue_size=max_queue_size,
            send=send,
            on_error=on_error,
            gzip=gzip,
            max_retries=max_retries,
            sync_mode=sync_mode,
            timeout=timeout,
        )

    return segment_analytics_client
