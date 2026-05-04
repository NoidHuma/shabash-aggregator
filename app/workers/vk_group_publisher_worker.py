import asyncio
import logging

from app.constants.streams import PREPARED_POSTS_STREAM
from app.constants.streams import VK_GROUP_PUBLISHER_GROUP
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.redis import redis_client
from app.modules.vk_publisher import VKPublisherClient
from app.services.post_formatter import format_post
from app.services.publish_policy import allowed_in_aggregator
from app.services.stream_service import StreamPostMessage
from app.services.stream_service import StreamService


logger = logging.getLogger(__name__)


CONSUMER_NAME = "vk_group_publisher_1"


class VKGroupPublisherWorker:

    def __init__(
        self,
        stream_service: StreamService,
        publisher: VKPublisherClient,
        input_stream: str = PREPARED_POSTS_STREAM,
        group: str = VK_GROUP_PUBLISHER_GROUP,
        consumer: str = CONSUMER_NAME,
    ) -> None:
        self._stream_service = stream_service
        self._publisher = publisher
        self._input_stream = input_stream
        self._group = group
        self._consumer = consumer

    async def run(self) -> None:
        logger.info(
            "VK group publisher started, reading '%s' (group '%s')",
            self._input_stream,
            self._group,
        )

        while True:
            for message in await self._stream_service.claim_stale_posts(
                stream=self._input_stream, group=self._group, consumer=self._consumer
            ):
                await self._handle_message(message)

            for message in await self._stream_service.read_posts(
                stream=self._input_stream, group=self._group, consumer=self._consumer
            ):
                await self._handle_message(message)

    async def _handle_message(self, message: StreamPostMessage) -> None:
        post = message.post

        if not allowed_in_aggregator(post):
            await self._stream_service.ack(
                stream=self._input_stream, group=self._group, message_id=message.message_id
            )
            logger.info("post id=%s пропущен (постоянная/вахта) — не для сообщества", post.id)
            return

        try:
            await self._publisher.publish(format_post(post), post.attachments)
        except Exception:
            # Не ack — заявка останется pending и переопубликуется позже.
            logger.exception("VK publish failed for post id=%s, leaving pending", post.id)
            return

        await self._stream_service.ack(
            stream=self._input_stream, group=self._group, message_id=message.message_id
        )
        logger.info("post id=%s published to VK community", post.id)
        await asyncio.sleep(settings.publish_min_interval)


async def main() -> None:
    setup_logging()

    worker = VKGroupPublisherWorker(
        stream_service=StreamService(redis_client=redis_client),
        publisher=VKPublisherClient(),
    )

    try:
        await worker.run()
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("VK group publisher stopping")
    finally:
        await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
