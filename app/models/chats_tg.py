from sqlalchemy import BigInteger
from sqlalchemy import Boolean
from sqlalchemy import Text

from sqlalchemy.orm import mapped_column

from app.db.database import Base


class ChatTG(Base):

    __tablename__ = "chats_tg"

    id = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True
    )

    chat_id = mapped_column(
        BigInteger,
        unique=True,
        nullable=False
    )

    title = mapped_column(
        Text,
        nullable=False
    )

    url = mapped_column(
        Text,
        nullable=False
    )

    is_active = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )