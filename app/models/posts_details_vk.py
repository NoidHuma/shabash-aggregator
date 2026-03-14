from sqlalchemy import BigInteger
from sqlalchemy import ForeignKey
from sqlalchemy import UniqueConstraint

from sqlalchemy.orm import mapped_column

from app.db.database import Base


class PostDetailsVK(Base):

    __tablename__ = "posts_details_vk"

    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "vk_post_id"
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

    vk_post_id = mapped_column(
        BigInteger,
        nullable=False
    )

    owner_id = mapped_column(
        BigInteger,
        nullable=False
    )

    from_id = mapped_column(
        BigInteger,
        nullable=True
    )