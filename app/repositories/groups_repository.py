from sqlalchemy import select
from sqlalchemy import update

from app.models.groups_vk import GroupVK


class GroupsRepository:

    async def create(
        self,
        session,
        group: GroupVK,
    ) -> GroupVK:

        session.add(group)

        await session.flush()

        return group

    async def get_active_groups(
        self,
        session,
    ) -> list[GroupVK]:

        stmt = (
            select(GroupVK)
            .where(GroupVK.is_active.is_(True))
        )

        result = await session.execute(stmt)

        return list(result.scalars().all())

    async def get_by_group_id(
        self,
        session,
        group_id: int,
    ) -> GroupVK | None:

        stmt = (
            select(GroupVK)
            .where(GroupVK.group_id == group_id)
        )

        result = await session.execute(stmt)

        return result.scalar_one_or_none()

    async def update_last_seen_post_id(
        self,
        session,
        group_id: int,
        last_seen_post_id: int,
    ) -> None:

        stmt = (
            update(GroupVK)
            .where(GroupVK.group_id == group_id)
            .values(last_seen_post_id=last_seen_post_id)
        )

        await session.execute(stmt)
