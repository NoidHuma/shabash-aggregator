from sqlalchemy import BigInteger
from sqlalchemy import DateTime
from sqlalchemy import Enum
from sqlalchemy import Text

from sqlalchemy.orm import mapped_column

from app.db.database import Base
from app.enums.post_source import PostSource
from app.enums.post_status import PostStatus


class Post(Base):

    __tablename__ = "posts"

    id = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True
    )

    status = mapped_column(
        Enum(PostStatus),
        nullable=False
    )

    source = mapped_column(
        Enum(PostSource),
        nullable=False
    )

    text = mapped_column(
        Text,
        nullable=False
    )

    post_datetime = mapped_column(
        DateTime,
        nullable=False
    )

    created_at = mapped_column(
        DateTime,
        nullable=False
    )

    source_post_url = mapped_column(
        Text,
        nullable=False
    )

    source_chat_url = mapped_column(
        Text,
        nullable=False
    )

    text_hash = mapped_column(
        Text,
        nullable=False
    )