import asyncio
from datetime import datetime

from app.db.database import SessionLocal
from app.models.raw_post import RawPost


async def test():

    async with SessionLocal() as session:

        post = RawPost(
            source="tg",
            text="Тестовый пост",
            parsed_at=datetime.utcnow()
        )

        session.add(post)

        await session.commit()

        print("saved")


asyncio.run(test())