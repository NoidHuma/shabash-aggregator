from sqlalchemy import select

from app.models.groups_vk import GroupVK


class GroupsRepository:

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