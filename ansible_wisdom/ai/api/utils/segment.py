import logging
from typing import Any, Dict, Union

from django.conf import settings
from healthcheck.version_info import VersionInfo
from segment import analytics

logger = logging.getLogger(__name__)
version_info = VersionInfo()


def send_segment_event(event: Dict[str, Any], event_name: str, user_id: Union[str, None]) -> None:
    if not settings.SEGMENT_WRITE_KEY:
        logger.info("segment write key not set, skipping event")
        return

    if 'modelName' not in event:
        event['modelName'] = settings.ANSIBLE_AI_MODEL_NAME

    if 'imageTags' not in event:
        event['imageTags'] = version_info.image_tags

    try:
        analytics.track(
            str(user_id) if user_id else 'unknown',
            event_name,
            event,
        )
        logger.info("sent segment event: %s", event_name)
    except Exception as ex:
        logger.exception(
            f"An exception {ex.__class__} occurred in sending event to segment: %s", event_name
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
            }
            send_segment_event(event, "segmentError", str(user_id) if user_id else 'unknown')
