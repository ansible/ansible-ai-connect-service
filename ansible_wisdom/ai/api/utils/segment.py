import logging
from typing import Any, Dict, Union

from django.conf import settings
from segment import analytics

logger = logging.getLogger(__name__)


def send_segement_event(event: Dict[str, Any], event_name: str, user_id: Union[str, None]) -> None:
    if not settings.SEGMENT_WRITE_KEY:
        logger.info("segment write key not set, skipping event")
        return

    analytics.write_key = "5r1FsJAkhB1ZWnxxaMRPDav5RdVnyMLr"
    analytics.debug = settings.DEBUG
    analytics.send = True
    print("sending segment user_id: %s", user_id)
    print("sending segment event: %s", event)
    print("sending segment event_name: %s", event_name)
    analytics.track(
        str(user_id) if user_id else 'unknown',
        event_name,
        event,
    )
    logger.info("sent segment event: %s", event_name)
