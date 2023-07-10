import logging
import platform
from typing import Any, Dict, Union

from django.conf import settings
from healthcheck.version_info import VersionInfo
from segment import analytics
from users.models import User

from .jaeger import with_distributed_tracing

logger = logging.getLogger(__name__)
version_info = VersionInfo()


@with_distributed_tracing(
    name="Content Matching (send event to Segment)",
    description='Formats event (dictionary) and forwards to Segment',
    file=__file__,
    method='send_segment_event',
)
def send_segment_event(
    event: Dict[str, Any], event_name: str, user: Union[User, None], span_ctx
) -> None:
    if not settings.SEGMENT_WRITE_KEY:
        logger.info("segment write key not set, skipping event")
        return

    if 'modelName' not in event:
        event['modelName'] = settings.ANSIBLE_AI_MODEL_NAME

    if 'imageTags' not in event:
        event['imageTags'] = version_info.image_tags

    if 'hostname' not in event:
        event['hostname'] = platform.node()

    if 'groups' not in event:
        event['groups'] = list(user.groups.values_list('name', flat=True)) if user else []

    try:
        analytics.track(
            str(user.uuid) if (user and getattr(user, 'uuid', None)) else 'unknown',
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
            }
            send_segment_event(event, "segmentError", user)
