import asyncio
import logging

from app.constants.streams import COARSE_FILTER_GROUP
from app.constants.streams import NEW_POSTS_STREAM
from app.core.logging import setup_logging
from app.core.redis import redis_client
from app.services.stream_service import StreamService


logger = logging.getLogger(__name__)


CONSUMER_NAME = "coarse_filter_stub"


async def main() -> None:
    """
    Заглушка грубого фильтра.

    Читает поток new_posts через consumer group coarse_filter и логирует
    каждую дошедшую публикацию. Нужна только для того, чтобы вживую увидеть,
    что VK scraper доводит посты до этапа грубого фильтра. Настоящая
    фильтрация и отправка в candidate_posts будут реализованы отдельным этапом.
    """

    setup_logging()

    stream_service = StreamService(redis_client=redis_client)

    logger.info(
        "Coarse filter stub started, reading '%s' (group '%s')",
        NEW_POSTS_STREAM,
        COARSE_FILTER_GROUP,
    )

    try:
        while True:
            messages = await stream_service.read_posts(
                stream=NEW_POSTS_STREAM,
                group=COARSE_FILTER_GROUP,
                consumer=CONSUMER_NAME,
                count=10,
                block_ms=5000,
            )

            for message in messages:
                post = message.post

                logger.info(
                    "new_posts <- id=%s source=%s len(text)=%d attachments=%d url=%s",
                    post.id,
                    post.source.value,
                    len(post.text),
                    len(post.attachments),
                    post.source_post_url,
                )

                await stream_service.ack(
                    stream=NEW_POSTS_STREAM,
                    group=COARSE_FILTER_GROUP,
                    message_id=message.message_id,
                )
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Coarse filter stub stopping")
    finally:
        await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
