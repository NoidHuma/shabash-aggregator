from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.domain.post import Post as DomainPost
from app.enums.post_source import PostSource
from app.enums.post_status import PostStatus
from app.models.attachments import Attachment
from app.models.groups_vk import GroupVK
from app.models.posts import Post as PostModel
from app.models.posts_details_vk import PostDetailsVK


@dataclass
class VKPostMapping:
    post: PostModel
    owner_id: int
    vk_post_id: int
    from_id: int | None
    attachment_urls: list[str]


def map_vk_post(
    vk_post: dict[str, Any],
    group: GroupVK,
    text_hash: str,
) -> VKPostMapping:

    owner_id = get_owner_id(
        vk_post=vk_post,
        group=group,
    )

    vk_post_id = get_vk_post_id(
        vk_post=vk_post,
    )

    attachment_urls = extract_photo_urls(
        vk_post=vk_post,
    )

    post = PostModel(
        status=PostStatus.NEW,
        source=PostSource.VK,
        text=get_text(vk_post),
        post_datetime=get_post_datetime(vk_post),
        created_at=datetime.utcnow(),
        source_post_url=build_vk_post_url(
            owner_id=owner_id,
            vk_post_id=vk_post_id,
        ),
        source_chat_url=group.url,
        text_hash=text_hash,
    )

    return VKPostMapping(
        post=post,
        owner_id=owner_id,
        vk_post_id=vk_post_id,
        from_id=get_from_id(vk_post),
        attachment_urls=attachment_urls,
    )


def build_post_details_vk(
    mapping: VKPostMapping,
    post_id: int,
) -> PostDetailsVK:

    return PostDetailsVK(
        post_id=post_id,
        vk_post_id=mapping.vk_post_id,
        owner_id=mapping.owner_id,
        from_id=mapping.from_id,
    )


def build_attachment_models(
    post_id: int,
    attachment_urls: list[str],
) -> list[Attachment]:

    return [
        Attachment(
            post_id=post_id,
            url=url,
            position=position,
        )
        for position, url in enumerate(attachment_urls)
    ]


def build_domain_post(
    post_model: PostModel,
    attachment_urls: list[str],
) -> DomainPost:

    if post_model.id is None:
        raise ValueError("post_model.id must be set before building domain post")

    return DomainPost(
        id=post_model.id,
        source=post_model.source,
        text=post_model.text,
        source_post_url=post_model.source_post_url,
        source_chat_url=post_model.source_chat_url,
        attachments=attachment_urls,
        attributes=None,
    )


def build_vk_post_url(
    owner_id: int,
    vk_post_id: int,
) -> str:

    return f"https://vk.com/wall{owner_id}_{vk_post_id}"


def get_text(
    vk_post: dict[str, Any],
) -> str:

    return str(vk_post.get("text") or "")


def get_vk_post_id(
    vk_post: dict[str, Any],
) -> int:

    return int(vk_post["id"])


def get_owner_id(
    vk_post: dict[str, Any],
    group: GroupVK,
) -> int:

    owner_id = vk_post.get("owner_id")

    if owner_id is not None:
        return int(owner_id)

    return -int(group.group_id)


def get_from_id(
    vk_post: dict[str, Any],
) -> int | None:

    from_id = vk_post.get("from_id")

    if from_id is None:
        return None

    return int(from_id)


def get_post_datetime(
    vk_post: dict[str, Any],
) -> datetime:

    return datetime.utcfromtimestamp(
        int(vk_post["date"])
    )


def extract_photo_urls(
    vk_post: dict[str, Any],
) -> list[str]:

    attachment_urls: list[str] = []

    for attachment in vk_post.get("attachments") or []:
        if attachment.get("type") != "photo":
            continue

        photo = attachment.get("photo") or {}
        sizes = photo.get("sizes") or []

        if not sizes:
            continue

        best_size = max(
            sizes,
            key=_photo_size_area,
        )

        url = best_size.get("url")

        if url:
            attachment_urls.append(str(url))

    return attachment_urls


def _photo_size_area(
    size: dict[str, Any],
) -> int:

    width = int(size.get("width") or 0)
    height = int(size.get("height") or 0)

    return width * height
