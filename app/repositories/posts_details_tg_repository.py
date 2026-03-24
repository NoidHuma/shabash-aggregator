from sqlalchemy import select

from app.models.posts_details_tg import PostDetailsTG


class PostsDetailsTGRepository:

    async def create(
        self,
        session,
        details: PostDetailsTG,
    ) -> PostDetailsTG:

        session.add(details)

        await session.flush()

        return details

    async def exists_tg_message(
        self,
        session,
        chat_id: int,
        message_id: int,
    ) -> bool:

        stmt = (
            select(PostDetailsTG.id)
            .where(PostDetailsTG.chat_id == chat_id)
            .where(PostDetailsTG.message_id == message_id)
            .limit(1)
        )

        result = await session.execute(stmt)

        return result.scalar_one_or_none() is not None

    async def get_by_source_ids(
        self,
        session,
        chat_id: int,
        message_id: int,
    ) -> PostDetailsTG | None:

        stmt = (
            select(PostDetailsTG)
            .where(PostDetailsTG.chat_id == chat_id)
            .where(PostDetailsTG.message_id == message_id)
        )

        result = await session.execute(stmt)

        return result.scalar_one_or_none()
