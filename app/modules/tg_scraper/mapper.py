from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from typing import Any

from app.domain.post import Post as DomainPost
from app.enums.post_source import PostSource
from app.enums.post_status import PostStatus
from app.models.chats_tg import ChatTG
from app.models.posts import Post as PostModel
from app.models.posts_details_tg import PostDetailsTG


@dataclass
class TGMessageMapping:
    post: PostModel
    chat_id: int
    message_id: int
    sender_id: int | None


def is_processable_message(message: Any) -> bool:

    if not (message.raw_text or "").strip():
        return False

    if message.action is not None:
        return False

    if message.sticker is not None:
        return False

    if message.document is not None and message.video is None:
        return False

    return True


def map_tg_message(
    message: Any,
    chat: ChatTG,
    text_hash: str,
) -> TGMessageMapping:

    post = PostModel(
        status=PostStatus.NEW,
        source=PostSource.TG,
        text=get_text(message),
        post_datetime=get_message_datetime(message),
        created_at=datetime.utcnow(),
        source_post_url=build_message_url(chat=chat, message=message),
        source_chat_url=chat.url,
        text_hash=text_hash,
    )

    return TGMessageMapping(
        post=post,
        chat_id=int(chat.chat_id),
        message_id=int(message.id),
        sender_id=get_sender_id(message),
    )


def build_post_details_tg(
    mapping: TGMessageMapping,
    post_id: int,
) -> PostDetailsTG:

    return PostDetailsTG(
        post_id=post_id,
        message_id=mapping.message_id,
        chat_id=mapping.chat_id,
        sender_id=mapping.sender_id,
    )


def build_domain_post(
    post_model: PostModel,
) -> DomainPost:

    if post_model.id is None:
        raise ValueError("post_model.id must be set before building domain post")

    return DomainPost(
        id=post_model.id,
        source=post_model.source,
        text=post_model.text,
        source_post_url=post_model.source_post_url,
        source_chat_url=post_model.source_chat_url,
        attachments=[],
        attributes=None,
    )


def build_message_url(
    chat: ChatTG,
    message: Any,
) -> str:

    tg_chat = getattr(message, "chat", None)
    username = getattr(tg_chat, "username", None) if tg_chat is not None else None

    if username:
        return f"https://t.me/{username}/{message.id}"

    stripped_chat_id = str(chat.chat_id).replace("-100", "").replace("-", "")

    return f"https://t.me/c/{stripped_chat_id}/{message.id}"


def get_text(
    message: Any,
) -> str:

    return str(message.raw_text or "")


def get_message_datetime(
    message: Any,
) -> datetime:

    # message.date — aware datetime в UTC; приводим к naive UTC, как у VK.
    return message.date.astimezone(timezone.utc).replace(tzinfo=None)


def get_sender_id(
    message: Any,
) -> int | None:

    sender_id = message.sender_id

    if sender_id is None:
        return None

    return int(sender_id)
