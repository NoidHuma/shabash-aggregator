from app.domain.post import Post
from app.enums.duration_type import DurationType


_AGGREGATOR_EXCLUDED_DURATIONS = {DurationType.PERMANENT, DurationType.VAHTA}


def allowed_in_aggregator(post: Post) -> bool:
    duration = post.attributes.duration if post.attributes else None
    return duration not in _AGGREGATOR_EXCLUDED_DURATIONS
