from sqlalchemy import BigInteger
from sqlalchemy import DateTime
from sqlalchemy import JSON
from sqlalchemy import String
from sqlalchemy import Text

from sqlalchemy.orm import mapped_column

from app.db.database import Base


class RawPost(Base):

    __tablename__ = "raw_posts"

    id = mapped_column(
        BigInteger,
        primary_key=True
    )

    source = mapped_column(String)

    source_chat_url = mapped_column(Text)

    source_post_url = mapped_column(Text)

    text = mapped_column(Text)

    media_urls = mapped_column(JSON)

    created_at = mapped_column(DateTime)

    parsed_at = mapped_column(DateTime)