import asyncio
import logging

from app.constants.streams import ATTRIBUTE_EXTRACTOR_GROUP
from app.constants.streams import FILTERED_POSTS_STREAM
from app.constants.streams import PREPARED_POSTS_STREAM
from app.core.logging import setup_logging
from app.core.redis import redis_client
from app.db.database import SessionLocal
from app.enums.post_status import PostStatus
from app.modules.attribute_extractor.extractor import AttributeExtractor
from app.modules.attribute_extractor.extractor import build_extractor
from app.repositories.attributes_repository import AttributesRepository
from app.repositories.posts_repository import PostsRepository
from app.services.stream_service import StreamPostMessage
from app.services.stream_service import StreamService


logger = logging.getLogger(__name__)


CONSUMER_NAME = "attribute_extractor_1"


class AttributeExtractorWorker:

    def __init__(
        self,
        stream_service: StreamService,
        posts_repository: PostsRepository,
        attributes_repository: AttributesRepository,
        extractor: AttributeExtractor,
        input_stream: str = FILTERED_POSTS_STREAM,
        output_stream: str = PREPARED_POSTS_STREAM,
        group: str = ATTRIBUTE_EXTRACTOR_GROUP,
        consumer: str = CONSUMER_NAME,
    ) -> None:
        self._stream_service = stream_service
        self._posts_repository = posts_repository
        self._attributes_repository = attributes_repository
        self._extractor = extractor
        self._input_stream = input_stream
        self._output_stream = output_stream
        self._group = group
        self._consumer = consumer

    async def run(self) -> None:
        logger.info(
            "Attribute extractor worker started, reading '%s' (group '%s')",
            self._input_stream,
            self._group,
        )

        while True:
            for message in await self._stream_service.claim_stale_posts(
                stream=self._input_stream,
                group=self._group,
                consumer=self._consumer,
            ):
                await self._handle_message(message)

            messages = await self._stream_service.read_posts(
                stream=self._input_stream,
                group=self._group,
                consumer=self._consumer,
            )

            for message in messages:
                await self._handle_message(message)

    async def _handle_message(
        self,
        message: StreamPostMessage,
    ) -> None:

        post = message.post

        try:
            # extract может ходить в LLM (блокирующий вызов) — уводим в поток.
            attributes = await asyncio.to_thread(self._extractor.extract, post.text)
            post.attributes = attributes

            async with SessionLocal() as session:
                await self._attributes_repository.create_or_update(
                    session=session,
                    post_id=post.id,
                    attributes=attributes,
                )
                await self._posts_repository.update_status(
                    session=session,
                    post_id=post.id,
                    status=PostStatus.ATTRIBUTES_EXTRACTED,
                )
                await session.commit()

            await self._stream_service.publish_post(
                stream=self._output_stream,
                post=post,
            )

            logger.info(
                "post id=%s -> attributes_extracted (duration=%s work_type=%s)",
                post.id,
                attributes.duration.value,
                attributes.work_type.value,
            )
        except Exception:
            # Сбой LLM/валидации/БД — не подтверждаем, останется pending.
            logger.exception(
                "Failed to extract attributes for post id=%s, leaving it pending",
                post.id,
            )
            return

        await self._stream_service.ack(
            stream=self._input_stream,
            group=self._group,
            message_id=message.message_id,
        )


async def main() -> None:
    setup_logging()

    extractor = build_extractor()

    worker = AttributeExtractorWorker(
        stream_service=StreamService(redis_client=redis_client),
        posts_repository=PostsRepository(),
        attributes_repository=AttributesRepository(),
        extractor=extractor,
    )

    try:
        await worker.run()
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Attribute extractor worker stopping")
    finally:
        await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
