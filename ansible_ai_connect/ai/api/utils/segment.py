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
import json
import logging
import platform
from typing import Any, Dict

from attr import asdict
from django.conf import settings
from django.utils import timezone
from segment import analytics
from segment.analytics import Client
from segment.analytics.consumer import MAX_MSG_SIZE
from segment.analytics.request import DatetimeSerializer
from segment.analytics.utils import clean

from ansible_ai_connect.ai.api.telemetry.schema1 import ChatBotBaseEvent, PlanEntry
from ansible_ai_connect.healthcheck.version_info import VersionInfo
from ansible_ai_connect.users.models import User

from .seated_users_allow_list import ALLOW_LIST

logger = logging.getLogger(__name__)
version_info = VersionInfo()


def send_segment_group(group_id: str, group_type: str, group_value: str, user: User) -> None:
    if not settings.SEGMENT_WRITE_KEY:
        logger.debug("segment write key not set, skipping group")
        return
    try:
        analytics.group(
            str(user.uuid), group_id, {"group_type": group_type, "group_value": group_value}
        )

        logger.info("sent segment group: %s", group_id)
    except Exception as ex:
        logger.exception(
            f"An exception {ex.__class__} occurred in sending group to segment: %s",
            group_id,
        )


def send_segment_event(event: Dict[str, Any], event_name: str, user: User) -> None:
    if not settings.SEGMENT_WRITE_KEY:
        logger.info("segment write key not set, skipping event")
        return

    timestamp = timezone.now().isoformat()

    if "modelName" not in event:
        # Set an empty string if model name is not found in the event
        event["modelName"] = ""

    if "imageTags" not in event:
        event["imageTags"] = version_info.image_tags

    if "hostname" not in event:
        event["hostname"] = platform.node()

    if "groups" not in event:
        event["groups"] = list(user.groups.values_list("name", flat=True))

    if "rh_user_has_seat" not in event:
        event["rh_user_has_seat"] = getattr(user, "rh_user_has_seat", False)

    if "rh_user_org_id" not in event:
        event["rh_user_org_id"] = getattr(user, "org_id", None)

    if "timestamp" not in event:
        event["timestamp"] = timestamp

    if "plans" not in event and hasattr(user, "userplan_set"):
        event["plans"] = [asdict(PlanEntry.init(up)) for up in user.userplan_set.all()]

    if event["rh_user_has_seat"]:
        allow_list = ALLOW_LIST.get(event_name)
        if allow_list:
            event = redact_seated_users_data(event, allow_list)
        else:
            # If event should be tracked, please update ALLOW_LIST appropriately
            logger.error(f"It is not allowed to track {event_name} events for seated users")
            return

    base_send_segment_event(event, event_name, user, analytics)


def send_chatbot_event(event: ChatBotBaseEvent, event_name: str, user: User) -> None:
    if not settings.SEGMENT_WRITE_KEY:
        logger.info("segment write key not set, skipping event")
        return
    if is_segment_message_exceeds_limit(asdict(event)):
        # Prioritize the prompt and referenced documents.
        event.chat_response = ""
    base_send_segment_event(asdict(event), event_name, user, analytics)


def is_segment_message_exceeds_limit(msg_dict):
    msg_dict = clean(msg_dict)
    msg_size = len(json.dumps(msg_dict, cls=DatetimeSerializer).encode())
    if msg_size > MAX_MSG_SIZE:
        return True
    return False


def base_send_segment_event(
    event: Dict[str, Any], event_name: str, user: User, client: Client
) -> None:
    try:
        client.track(
            str(user.uuid) if getattr(user, "uuid", None) else "unknown",
            event_name,
            event,
        )
        logger.info("sent segment event: %s", event_name)
    except Exception as ex:
        logger.exception(
            f"An exception {ex.__class__} occurred in sending event to segment: %s",
            event_name,
        )
        args = getattr(ex, "args")
        # Log RuntimeError and send the error to Segment if it is for an event exceeding size limit
        if (
            isinstance(args, tuple)
            and args[0] == "Message exceeds %skb limit. (%s)"
            and len(args) == 3
        ):
            msg_len = len(args[2])
            logger.error(f"Message exceeds {args[1]}kb limit. msg_len={msg_len}")

            event = {
                "error_type": "event_exceeds_limit",
                "details": {
                    "event_name": event_name,
                    "msg_len": msg_len,
                },
                "timestamp": event["timestamp"],
            }
            send_segment_event(event, "segmentError", user)


def send_schema1_event(event_obj) -> None:
    if not settings.SEGMENT_WRITE_KEY:
        logger.info("segment write key not set, skipping event")
        return

    event_dict = event_obj.as_dict()
    if event_obj.rh_user_has_seat:
        allow_list = ALLOW_LIST.get(event_obj.event_name)
        if allow_list:
            event_dict = redact_seated_users_data(event_dict, allow_list)
        else:
            # If event should be tracked, please update ALLOW_LIST appropriately
            logger.error(
                f"It is not allowed to track {event_obj.event_name} events for seated users"
            )
            return

    base_send_segment_event(event_dict, event_obj.event_name, event_obj._user, analytics)


def redact_seated_users_data(event: Dict[str, Any], allow_list: Dict[str, Any]) -> Dict[str, Any]:
    """
    Copy a dictionary to another dictionary using a nested list of allowed keys.

    Args:
    - event (dict): The source dictionary to copy from.
    - allow_list (dict): The nested dictionary containing allowed keys.

    Returns:
    - dict: A new dictionary containing only the allowed nested keys from the source dictionary.
    """
    redacted_event = {}
    for key, sub_whitelist in (
        allow_list.items() if isinstance(allow_list, dict) else allow_list[0].items()
    ):
        if key in event:
            if isinstance(sub_whitelist, dict):
                if isinstance(event[key], dict):
                    redacted_event[key] = redact_seated_users_data(event[key], sub_whitelist)
                else:
                    redacted_event[key] = event[key]
            elif isinstance(sub_whitelist, list):
                redacted_event[key] = [
                    redact_seated_users_data(item, sub_whitelist) for item in event[key]
                ]
            else:
                redacted_event[key] = event[key]
    return redacted_event
