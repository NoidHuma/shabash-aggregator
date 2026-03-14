from sqlalchemy import BigInteger
from sqlalchemy import Enum
from sqlalchemy import ForeignKey
from sqlalchemy import Text

from sqlalchemy.orm import mapped_column

from app.db.database import Base
from app.enums.duration_type import DurationType
from app.enums.work_type import WorkType


class PostAttributes(Base):

    __tablename__ = "attributes"

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

    duration = mapped_column(
        Enum(DurationType),
        nullable=False
    )

    work_type = mapped_column(
        Enum(WorkType),
        nullable=False
    )

    payment = mapped_column(
        Text,
        nullable=True
    )

    address = mapped_column(
        Text,
        nullable=True
    )