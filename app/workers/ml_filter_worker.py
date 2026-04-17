import asyncio
import logging
import os

from app.constants.streams import CANDIDATE_POSTS_STREAM
from app.constants.streams import FILTERED_POSTS_STREAM
from app.constants.streams import ML_FILTER_GROUP
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.redis import redis_client
from app.db.database import SessionLocal
from app.enums.post_status import PostStatus
from app.modules.ml_filter.classifier import RelevanceClassifier
from app.repositories.posts_repository import PostsRepository
from app.services.stream_service import StreamPostMessage
from app.services.stream_service import StreamService


logger = logging.getLogger(__name__)


CONSUMER_NAME = "ml_filter_1"


class MLFilterWorker:

    def __init__(
        self,
        stream_service: StreamService,
        posts_repository: PostsRepository,
        classifier: RelevanceClassifier,
        input_stream: str = CANDIDATE_POSTS_STREAM,
        output_stream: str = FILTERED_POSTS_STREAM,
        group: str = ML_FILTER_GROUP,
        consumer: str = CONSUMER_NAME,
    ) -> None:
        self._stream_service = stream_service
        self._posts_repository = posts_repository
        self._classifier = classifier
        self._input_stream = input_stream
        self._output_stream = output_stream
        self._group = group
        self._consumer = consumer

    async def run(self) -> None:
        logger.info(
            "ML filter worker started, reading '%s' (group '%s'), threshold=%.3f",
            self._input_stream,
            self._group,
            self._classifier.threshold,
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
            proba = self._classifier.predict_proba(post.text)
            relevant = proba >= self._classifier.threshold

            status = (
                PostStatus.ML_FILTER_PASSED
                if relevant
                else PostStatus.ML_FILTER_REJECTED
            )

            async with SessionLocal() as session:
                await self._posts_repository.update_status(
                    session=session,
                    post_id=post.id,
                    status=status,
                )
                await session.commit()

            if relevant:
                await self._stream_service.publish_post(
                    stream=self._output_stream,
                    post=post,
                )

            logger.info(
                "post id=%s proba=%.3f -> %s",
                post.id,
                proba,
                status.value,
            )
        except Exception:
            # Сообщение не подтверждаем — останется pending и переобработается.
            logger.exception(
                "Failed to ML-filter post id=%s, leaving it pending",
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

    if not os.path.exists(settings.ml_model_path):
        logger.error(
            "Модель не найдена: %s. Сначала обучи её: python -m app.ml.train",
            settings.ml_model_path,
        )
        return

    classifier = RelevanceClassifier.load(settings.ml_model_path)
    logger.info(
        "Загружена модель %s (порог %.3f, метаданные: %s)",
        settings.ml_model_path,
        classifier.threshold,
        classifier.metadata,
    )

    worker = MLFilterWorker(
        stream_service=StreamService(redis_client=redis_client),
        posts_repository=PostsRepository(),
        classifier=classifier,
    )

    try:
        await worker.run()
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("ML filter worker stopping")
    finally:
        await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
