import asyncio
import logging

from app.constants.streams import CANDIDATE_POSTS_STREAM
from app.constants.streams import COARSE_FILTER_GROUP
from app.constants.streams import NEW_POSTS_STREAM
from app.core.logging import setup_logging
from app.core.redis import redis_client
from app.db.database import SessionLocal
from app.enums.post_status import PostStatus
from app.modules.coarse_filter.filter import passes_coarse_filter
from app.repositories.posts_repository import PostsRepository
from app.services.stream_service import StreamPostMessage
from app.services.stream_service import StreamService


logger = logging.getLogger(__name__)


CONSUMER_NAME = "coarse_filter_1"


class CoarseFilterWorker:

    def __init__(
        self,
        stream_service: StreamService,
        posts_repository: PostsRepository,
        input_stream: str = NEW_POSTS_STREAM,
        output_stream: str = CANDIDATE_POSTS_STREAM,
        group: str = COARSE_FILTER_GROUP,
        consumer: str = CONSUMER_NAME,
    ) -> None:
        self._stream_service = stream_service
        self._posts_repository = posts_repository
        self._input_stream = input_stream
        self._output_stream = output_stream
        self._group = group
        self._consumer = consumer

    async def run(self) -> None:
        logger.info(
            "Coarse filter worker started, reading '%s' (group '%s')",
            self._input_stream,
            self._group,
        )

        while True:
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
            passed = passes_coarse_filter(post)

            status = (
                PostStatus.COARSE_FILTER_PASSED
                if passed
                else PostStatus.COARSE_FILTER_REJECTED
            )

            async with SessionLocal() as session:
                await self._posts_repository.update_status(
                    session=session,
                    post_id=post.id,
                    status=status,
                )
                await session.commit()

            if passed:
                await self._stream_service.publish_post(
                    stream=self._output_stream,
                    post=post,
                )

            logger.info(
                "post id=%s len(text)=%d -> %s",
                post.id,
                len(post.text),
                status.value,
            )
        except Exception:
            # Сообщение не подтверждаем: оно останется pending в группе
            # и будет переобработано. Один сбой не должен валить worker.
            logger.exception(
                "Failed to process post id=%s, leaving it pending",
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

    worker = CoarseFilterWorker(
        stream_service=StreamService(redis_client=redis_client),
        posts_repository=PostsRepository(),
    )

    try:
        await worker.run()
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Coarse filter worker stopping")
    finally:
        await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
