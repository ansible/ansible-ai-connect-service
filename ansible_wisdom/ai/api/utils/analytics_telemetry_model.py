from enum import Enum

from attr import Factory, field, frozen
from attrs import validators
from django.utils import timezone


class AnalyticsTelemetryEvents(Enum):
    RECOMMENDATION_GENERATED = "Recommendation Generated"
    RECOMMENDATION_ACTION = "Recommendation Action"
    PRODUCT_FEEDBACK = "Product Feedback"


@frozen
class AnalyticsRecommendationTask:
    collection: str = field(validator=validators.instance_of(str), converter=str, default='')
    module: str = field(validator=validators.instance_of(str), converter=str, default='')


@frozen
class AnalyticsRecommendationGenerated:
    tasks: list[AnalyticsRecommendationTask] = field(factory=list, validator=validators.min_len(1))
    suggestion_id: str = field(validator=validators.instance_of(str), converter=str, default='')
    rh_user_org_id: int = field(validator=validators.instance_of(int), converter=int, default=0)
    model_name: str = field(default='')
    timestamp: str = field(
        default=Factory(lambda self: timezone.now().isoformat(), takes_self=True)
    )


@frozen
class AnalyticsRecommendationAction:
    action: int = field(
        validator=[validators.instance_of(int), validators.in_([0, 1, 2])], converter=int
    )
    suggestion_id: str = field(validator=validators.instance_of(str), converter=str, default='')
    rh_user_org_id: int = field(validator=validators.instance_of(int), converter=int, default=0)
    timestamp: str = field(
        default=Factory(lambda self: timezone.now().isoformat(), takes_self=True)
    )


@frozen
class AnalyticsProductFeedback:
    value: int = field(
        validator=[validators.instance_of(int), validators.in_([1, 2, 3, 4, 5])], converter=int
    )
    rh_user_org_id: int = field(validator=validators.instance_of(int), converter=int, default=0)
    timestamp: str = field(
        default=Factory(lambda self: timezone.now().isoformat(), takes_self=True)
    )
