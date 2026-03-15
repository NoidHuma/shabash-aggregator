from sqlalchemy import select

from app.models.chats_tg import ChatTG


class ChatsRepository:

    async def get_active_chats(
        self,
        session,
    ) -> list[ChatTG]:

        stmt = (
            select(ChatTG)
            .where(ChatTG.is_active.is_(True))
        )

        result = await session.execute(stmt)

        return list(result.scalars().all())