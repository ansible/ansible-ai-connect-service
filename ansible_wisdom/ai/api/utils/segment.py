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

    analytics.track(
        str(user_id) if user_id else 'unknown',
        event_name,
        event,
    )
    logger.info("sent segment event: %s", event_name)
