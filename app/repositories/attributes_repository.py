from sqlalchemy import select

from app.domain.post_attributes import PostAttributes as PostAttributesDomain
from app.models.post_attributes import PostAttributes


class AttributesRepository:

    async def create(
        self,
        session,
        attributes: PostAttributes,
    ) -> PostAttributes:

        session.add(attributes)

        await session.flush()

        return attributes

    async def get_by_post_id(
        self,
        session,
        post_id: int,
    ) -> PostAttributes | None:

        stmt = (
            select(PostAttributes)
            .where(PostAttributes.post_id == post_id)
        )

        result = await session.execute(stmt)

        return result.scalar_one_or_none()

    async def create_or_update(
        self,
        session,
        post_id: int,
        attributes: PostAttributesDomain,
    ) -> PostAttributes:
        """
        Сохраняет атрибуты заявки. Если запись для post_id уже есть —
        обновляет (защита от UNIQUE(post_id) при повторной обработке).
        """

        existing = await self.get_by_post_id(session=session, post_id=post_id)

        if existing is not None:
            existing.duration = attributes.duration
            existing.work_type = attributes.work_type
            existing.payment = attributes.payment
            existing.address = attributes.address
            await session.flush()
            return existing

        model = PostAttributes(
            post_id=post_id,
            duration=attributes.duration,
            work_type=attributes.work_type,
            payment=attributes.payment,
            address=attributes.address,
        )
        session.add(model)
        await session.flush()
        return model
