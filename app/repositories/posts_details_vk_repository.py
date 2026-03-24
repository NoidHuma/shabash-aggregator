from sqlalchemy import select

from app.models.posts_details_vk import PostDetailsVK


class PostsDetailsVKRepository:

    async def create(
        self,
        session,
        details: PostDetailsVK,
    ) -> PostDetailsVK:

        session.add(details)

        await session.flush()

        return details

    async def exists_vk_post(
        self,
        session,
        owner_id: int,
        vk_post_id: int,
    ) -> bool:

        stmt = (
            select(PostDetailsVK.id)
            .where(PostDetailsVK.owner_id == owner_id)
            .where(PostDetailsVK.vk_post_id == vk_post_id)
            .limit(1)
        )

        result = await session.execute(stmt)

        return result.scalar_one_or_none() is not None

    async def get_by_source_ids(
        self,
        session,
        owner_id: int,
        vk_post_id: int,
    ) -> PostDetailsVK | None:

        stmt = (
            select(PostDetailsVK)
            .where(PostDetailsVK.owner_id == owner_id)
            .where(PostDetailsVK.vk_post_id == vk_post_id)
        )

        result = await session.execute(stmt)

        return result.scalar_one_or_none()
