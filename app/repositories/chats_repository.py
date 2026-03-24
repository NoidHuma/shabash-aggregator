from sqlalchemy import select
from sqlalchemy import update

from app.models.chats_tg import ChatTG


class ChatsRepository:

    async def create(
        self,
        session,
        chat: ChatTG,
    ) -> ChatTG:

        session.add(chat)

        await session.flush()

        return chat

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

    async def get_by_chat_id(
        self,
        session,
        chat_id: int,
    ) -> ChatTG | None:

        stmt = (
            select(ChatTG)
            .where(ChatTG.chat_id == chat_id)
        )

        result = await session.execute(stmt)

        return result.scalar_one_or_none()

    async def update_last_seen_message_id(
        self,
        session,
        chat_id: int,
        last_seen_message_id: int,
    ) -> None:

        stmt = (
            update(ChatTG)
            .where(ChatTG.chat_id == chat_id)
            .values(last_seen_message_id=last_seen_message_id)
        )

        await session.execute(stmt)
