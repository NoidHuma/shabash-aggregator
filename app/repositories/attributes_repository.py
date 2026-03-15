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