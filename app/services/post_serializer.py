import json
from typing import Any

from app.domain.post import Post
from app.domain.post_attributes import PostAttributes
from app.enums.duration_type import DurationType
from app.enums.post_source import PostSource
from app.enums.work_type import WorkType


def serialize_post(post: Post) -> dict[str, str]:

    payload = {
        "id": post.id,
        "source": post.source.value,
        "text": post.text,
        "source_post_url": post.source_post_url,
        "source_chat_url": post.source_chat_url,
        "attachments": post.attachments,
        "attributes": _serialize_attributes(post.attributes),
    }

    return {
        "payload": json.dumps(
            payload,
            ensure_ascii=False,
        )
    }


def deserialize_post(data: dict[str, Any]) -> Post:

    payload_raw = data["payload"]

    if isinstance(payload_raw, bytes):
        payload_raw = payload_raw.decode("utf-8")

    payload = json.loads(payload_raw)

    return Post(
        id=int(payload["id"]),
        source=PostSource(payload["source"]),
        text=payload["text"],
        source_post_url=payload["source_post_url"],
        source_chat_url=payload["source_chat_url"],
        attachments=list(payload["attachments"]),
        attributes=_deserialize_attributes(payload["attributes"]),
    )


def _serialize_attributes(
    attributes: PostAttributes | None,
) -> dict[str, str | None] | None:

    if attributes is None:
        return None

    return {
        "duration": attributes.duration.value,
        "work_type": attributes.work_type.value,
        "payment": attributes.payment,
        "address": attributes.address,
    }


def _deserialize_attributes(
    payload: dict[str, str | None] | None,
) -> PostAttributes | None:

    if payload is None:
        return None

    return PostAttributes(
        duration=DurationType(payload["duration"]),
        work_type=WorkType(payload["work_type"]),
        payment=payload["payment"],
        address=payload["address"],
    )
