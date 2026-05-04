from app.domain.post import Post
from app.enums.duration_type import DurationType


# В агрегирующие канал/сообщество не публикуем постоянную работу и вахту —
# только разовые (короткие/на смену) и с неопределённой длительностью.
# В личные боты при этом приходят все длительности (если проходят фильтры).
_AGGREGATOR_EXCLUDED_DURATIONS = {DurationType.PERMANENT, DurationType.VAHTA}


def allowed_in_aggregator(post: Post) -> bool:
    """True, если заявку можно постить в общий канал/сообщество."""
    duration = post.attributes.duration if post.attributes else None
    return duration not in _AGGREGATOR_EXCLUDED_DURATIONS
