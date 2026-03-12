from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


DATABASE_URL = settings.database_url

engine = create_async_engine(
    DATABASE_URL,
    echo=True
)

SessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False
)


class Base(DeclarativeBase):
    pass