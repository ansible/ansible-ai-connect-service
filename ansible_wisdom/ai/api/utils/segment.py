import logging
import platform
from typing import Any, Dict

from django.conf import settings
from django.utils import timezone
from healthcheck.version_info import VersionInfo
from segment import analytics
from segment.analytics import Client
from users.models import User

from .seated_users_allow_list import ALLOW_LIST

logger = logging.getLogger(__name__)
version_info = VersionInfo()


def send_segment_group(group_id: str, group_type: str, group_value: str, user: User) -> None:
    if not settings.SEGMENT_WRITE_KEY:
        logger.debug("segment write key not set, skipping group")
        return
    try:
        analytics.group(
            str(user.uuid), group_id, {'group_type': group_type, 'group_value': group_value}
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

    if 'modelName' not in event:
        # Set an empty string if model name is not found in the event
        event['modelName'] = ''

    if 'imageTags' not in event:
        event['imageTags'] = version_info.image_tags

    if 'hostname' not in event:
        event['hostname'] = platform.node()

    if 'groups' not in event:
        event['groups'] = list(user.groups.values_list('name', flat=True))

    if 'rh_user_has_seat' not in event:
        event['rh_user_has_seat'] = getattr(user, 'rh_user_has_seat', False)

    if 'rh_user_org_id' not in event:
        event['rh_user_org_id'] = getattr(user, 'org_id', None)

    if 'timestamp' not in event:
        event['timestamp'] = timestamp

    if event['rh_user_has_seat']:
        allow_list = ALLOW_LIST.get(event_name)

        if allow_list:
            event = redact_seated_users_data(event, allow_list)
        else:
            # If event should be tracked, please update ALLOW_LIST appropriately
            logger.error(f'It is not allowed to track {event_name} events for seated users')
            return
    base_send_segment_event(event, event_name, user, analytics)


def base_send_segment_event(
    event: Dict[str, Any], event_name: str, user: User, client: Client
) -> None:
    try:
        client.track(
            str(user.uuid) if getattr(user, 'uuid', None) else 'unknown',
            event_name,
            event,
        )
        logger.info("sent segment event: %s", event_name)
    except Exception as ex:
        logger.exception(
            f"An exception {ex.__class__} occurred in sending event to segment: %s",
            event_name,
        )
        args = getattr(ex, 'args')
        # Log RuntimeError and send the error to Segment if it is for an event exceeding size limit
        if (
            isinstance(args, tuple)
            and args[0] == 'Message exceeds %skb limit. (%s)'
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
                "timestamp": event['timestamp'],
            }
            send_segment_event(event, "segmentError", user)


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
