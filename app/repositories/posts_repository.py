from datetime import datetime
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy import update

from app.models.posts import Post


class PostsRepository:

    async def create_post(
        self,
        session,
        post: Post,
    ) -> Post:
        session.add(post)

        await session.flush()

        return post

    async def update_status(
        self,
        session,
        post_id: int,
        status,
    ) -> None:

        stmt = (
            update(Post)
            .where(Post.id == post_id)
            .values(status=status)
        )

        await session.execute(stmt)

    async def get_by_id(
        self,
        session,
        post_id: int,
    ) -> Post | None:

        stmt = (
            select(Post)
            .where(Post.id == post_id)
        )

        result = await session.execute(stmt)

        return result.scalar_one_or_none()

    async def exists_hash_last_hour(
        self,
        session,
        text_hash: str,
    ) -> bool:

        border = datetime.utcnow() - timedelta(hours=1)

        stmt = (
            select(Post.id)
            .where(Post.text_hash == text_hash)
            .where(Post.created_at >= border)
            .limit(1)
        )

        result = await session.execute(stmt)

        return result.scalar_one_or_none() is not None