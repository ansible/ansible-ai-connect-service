import logging
from typing import Any, Dict, Union

from django.conf import settings
from segment import analytics

logger = logging.getLogger(__name__)


def send_segment_event(event: Dict[str, Any], event_name: str, user_id: Union[str, None]) -> None:
    if not settings.SEGMENT_WRITE_KEY:
        logger.info("segment write key not set, skipping event")
        return

    analytics.track(
        str(user_id) if user_id else 'unknown',
        event_name,
        event,
    )
    logger.info("sent segment event: %s", event_name)
