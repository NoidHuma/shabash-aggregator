from app.models.attachments import Attachment


class AttachmentsRepository:

    async def create_many(
        self,
        session,
        attachments: list[Attachment],
    ) -> None:

        session.add_all(attachments)

        await session.flush()