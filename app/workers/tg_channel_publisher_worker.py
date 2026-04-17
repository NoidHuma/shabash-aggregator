import asyncio
import logging

from app.constants.streams import PREPARED_POSTS_STREAM
from app.constants.streams import TG_CHANNEL_PUBLISHER_GROUP
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.redis import redis_client
from app.modules.tg_publisher import TGPublisherClient
from app.services.post_formatter import format_post
from app.services.stream_service import StreamPostMessage
from app.services.stream_service import StreamService


logger = logging.getLogger(__name__)


CONSUMER_NAME = "tg_channel_publisher_1"


class TGChannelPublisherWorker:

    def __init__(
        self,
        stream_service: StreamService,
        publisher: TGPublisherClient,
        input_stream: str = PREPARED_POSTS_STREAM,
        group: str = TG_CHANNEL_PUBLISHER_GROUP,
        consumer: str = CONSUMER_NAME,
    ) -> None:
        self._stream_service = stream_service
        self._publisher = publisher
        self._input_stream = input_stream
        self._group = group
        self._consumer = consumer

    async def run(self) -> None:
        logger.info(
            "TG channel publisher started, reading '%s' (group '%s')",
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
        try:
            await self._publisher.publish(format_post(post), post.attachments)
        except Exception:
            logger.exception("TG publish failed for post id=%s, leaving pending", post.id)
            return

        await self._stream_service.ack(
            stream=self._input_stream, group=self._group, message_id=message.message_id
        )
        logger.info("post id=%s published to TG channel", post.id)
        await asyncio.sleep(settings.publish_min_interval)


async def main() -> None:
    setup_logging()

    worker = TGChannelPublisherWorker(
        stream_service=StreamService(redis_client=redis_client),
        publisher=TGPublisherClient(),
    )

    try:
        await worker.run()
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("TG channel publisher stopping")
    finally:
        await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
