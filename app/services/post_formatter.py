from app.domain.post import Post
from app.enums.duration_type import DurationType
from app.enums.post_source import PostSource
from app.enums.work_type import WorkType


_UNKNOWN_TEXT = "не удалось определить"

_SOURCE_LABEL = {
    PostSource.VK: "VK",
    PostSource.TG: "Telegram",
}

_DURATION_LABEL = {
    DurationType.PERMANENT: "Постоянная работа",
    DurationType.FULL_SHIFT: "Разовая заявка на целую смену",
    DurationType.SHORT_TASK: "Разовая быстрая заявка",
    DurationType.VAHTA: "Вахта",
    DurationType.UNKNOWN: _UNKNOWN_TEXT,
}

_WORK_TYPE_LABEL = {
    WorkType.LOADER: "Грузчик",
    WorkType.HANDYMAN: "Разнорабочий",
    WorkType.SPECIALIST: "Специалист",
    WorkType.UNKNOWN: _UNKNOWN_TEXT,
}


def format_post(post: Post, header: str = "🔥 Новая заявка! 🔥") -> str:
    """Собирает текст заявки для публикации в едином формате."""

    source = _SOURCE_LABEL.get(post.source, str(post.source))

    attrs = post.attributes
    duration = _DURATION_LABEL.get(attrs.duration, _UNKNOWN_TEXT) if attrs else _UNKNOWN_TEXT
    work_type = _WORK_TYPE_LABEL.get(attrs.work_type, _UNKNOWN_TEXT) if attrs else _UNKNOWN_TEXT
    payment = (attrs.payment if attrs and attrs.payment else _UNKNOWN_TEXT)
    address = (attrs.address if attrs and attrs.address else _UNKNOWN_TEXT)

    return (
        f"{header}\n\n"
        f"Источник - {source}, {post.source_chat_url}\n"
        f"Исходная публикация - {post.source_post_url}\n\n"
        "Исходный текст:\n"
        f"{post.text}\n\n"
        f"🕒 Длительность - {duration}\n"
        f"🔨 Характер работы - {work_type}\n"
        f"💵 Оплата - {payment}\n"
        f"📍 Адрес - {address}"
    )
