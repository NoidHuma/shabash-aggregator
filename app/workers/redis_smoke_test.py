import asyncio
import logging

from app.constants.streams import NEW_POSTS_STREAM
from app.core.logging import setup_logging
from app.core.redis import redis_client
from app.domain.post import Post
from app.enums.post_source import PostSource
from app.services.stream_service import StreamService


logger = logging.getLogger(__name__)


async def main() -> None:
    setup_logging()

    stream_service = StreamService(
        redis_client=redis_client,
    )

    post = Post(
        id=1,
        source=PostSource.VK,
        text="Test post: need to carry out trash. Payment 2000 rub.",
        source_post_url="https://vk.com/wall-1_1",
        source_chat_url="https://vk.com/test_group",
        attachments=[],
        attributes=None,
    )

    logger.info("Publishing test post to Redis stream '%s'", NEW_POSTS_STREAM)

    published_message_id = await stream_service.publish_post(
        stream=NEW_POSTS_STREAM,
        post=post,
    )

    logger.info("Published message id: %s", published_message_id)

    messages = await stream_service.read_posts(
        stream=NEW_POSTS_STREAM,
        group="redis_smoke_test_group",
        consumer="redis_smoke_test_consumer",
        count=1,
        block_ms=1000,
    )

    if not messages:
        logger.error("No messages were read from Redis")
        return

    for message in messages:
        logger.info("Read message id: %s", message.message_id)
        logger.info("Read post: %s", message.post)

        await stream_service.ack(
            stream=message.stream,
            group="redis_smoke_test_group",
            message_id=message.message_id,
        )

        logger.info("Message acknowledged")

    await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
