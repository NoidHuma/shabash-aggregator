from datetime import datetime

from sqlalchemy import BigInteger
from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import Integer
from sqlalchemy import JSON
from sqlalchemy import Text
from sqlalchemy.orm import mapped_column

from app.db.database import Base


class _BotUserMixin:

    id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    external_id = mapped_column(BigInteger, unique=True, nullable=False)


    status = mapped_column(Text, nullable=False, default="active")


    src_vk = mapped_column(Boolean, nullable=False, default=True)
    src_tg = mapped_column(Boolean, nullable=False, default=True)

    payment_required = mapped_column(Boolean, nullable=False, default=False)
    address_required = mapped_column(Boolean, nullable=False, default=False)

    wt_loader = mapped_column(Boolean, nullable=False, default=True)
    wt_handyman = mapped_column(Boolean, nullable=False, default=True)
    wt_specialist = mapped_column(Boolean, nullable=False, default=True)
    wt_unknown = mapped_column(Boolean, nullable=False, default=True)

    dur_short_task = mapped_column(Boolean, nullable=False, default=True)
    dur_full_shift = mapped_column(Boolean, nullable=False, default=True)
    dur_permanent = mapped_column(Boolean, nullable=False, default=True)
    dur_vahta = mapped_column(Boolean, nullable=False, default=True)
    dur_unknown = mapped_column(Boolean, nullable=False, default=True)


    wizard_step = mapped_column(Integer, nullable=True)
    wizard_draft = mapped_column(JSON, nullable=True)
    wizard_mode = mapped_column(Text, nullable=True)


    created_at = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class TGBotUser(Base, _BotUserMixin):
    __tablename__ = "tg_bot_users"


class VKBotUser(Base, _BotUserMixin):
    __tablename__ = "vk_bot_users"
