from dataclasses import dataclass

from app.domain.post_attributes import PostAttributes
from app.enums.post_source import PostSource


@dataclass
class Post:
    id: int

    source: PostSource

    text: str

    source_post_url: str
    source_chat_url: str

    attachments: list[str]

    attributes: PostAttributes | None