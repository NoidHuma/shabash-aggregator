from app.domain.post import Post
from app.enums.duration_type import DurationType
from app.enums.work_type import WorkType


def matches(user, post: Post) -> bool:
    """True, если заявка проходит все пользовательские фильтры (логика И)."""

    attrs = post.attributes
    duration = attrs.duration if attrs else DurationType.UNKNOWN
    work_type = attrs.work_type if attrs else WorkType.UNKNOWN
    payment = attrs.payment if attrs else None
    address = attrs.address if attrs else None

    if user.payment_required and not payment:
        return False
    if user.address_required and not address:
        return False

    work_flag = {
        WorkType.LOADER: user.wt_loader,
        WorkType.HANDYMAN: user.wt_handyman,
        WorkType.SPECIALIST: user.wt_specialist,
        WorkType.UNKNOWN: user.wt_unknown,
    }[work_type]
    if not work_flag:
        return False

    duration_flag = {
        DurationType.SHORT_TASK: user.dur_short_task,
        DurationType.FULL_SHIFT: user.dur_full_shift,
        DurationType.PERMANENT: user.dur_permanent,
        DurationType.VAHTA: user.dur_vahta,
        DurationType.UNKNOWN: user.dur_unknown,
    }[duration]
    if not duration_flag:
        return False

    return True
