from sqlalchemy import BigInteger
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import Text

from sqlalchemy.orm import mapped_column

from app.db.database import Base


class Attachment(Base):

    __tablename__ = "attachments"

    id = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True
    )

    post_id = mapped_column(
        ForeignKey("posts.id"),
        nullable=False
    )

    url = mapped_column(
        Text,
        nullable=False
    )

    position = mapped_column(
        Integer,
        nullable=False
    )