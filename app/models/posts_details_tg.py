from sqlalchemy import BigInteger
from sqlalchemy import ForeignKey
from sqlalchemy import UniqueConstraint

from sqlalchemy.orm import mapped_column

from app.db.database import Base


class PostDetailsTG(Base):

    __tablename__ = "posts_details_tg"

    __table_args__ = (
        UniqueConstraint(
            "chat_id",
            "message_id"
        ),
    )

    id = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True
    )

    post_id = mapped_column(
        ForeignKey("posts.id"),
        unique=True,
        nullable=False
    )

    message_id = mapped_column(
        BigInteger,
        nullable=False
    )

    chat_id = mapped_column(
        BigInteger,
        nullable=False
    )

    sender_id = mapped_column(
        BigInteger,
        nullable=True
    )