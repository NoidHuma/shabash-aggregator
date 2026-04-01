import logging
from typing import Any

from app.constants.streams import NEW_POSTS_STREAM
from app.core.config import settings
from app.domain.post import Post as DomainPost
from app.models.chats_tg import ChatTG
from app.modules.tg_scraper.mapper import build_domain_post
from app.modules.tg_scraper.mapper import build_post_details_tg
from app.modules.tg_scraper.mapper import is_processable_message
from app.modules.tg_scraper.mapper import map_tg_message
from app.modules.tg_scraper.tg_client import TGClient
from app.repositories.chats_repository import ChatsRepository
from app.repositories.posts_details_tg_repository import PostsDetailsTGRepository
from app.repositories.posts_repository import PostsRepository
from app.services.hash_service import calculate_text_hash
from app.services.stream_service import StreamService


logger = logging.getLogger(__name__)


class TGScraper:

    def __init__(
        self,
        tg_client: TGClient,
        posts_repository: PostsRepository,
        posts_details_tg_repository: PostsDetailsTGRepository,
        chats_repository: ChatsRepository,
        stream_service: StreamService,
        output_stream: str = NEW_POSTS_STREAM,
        messages_per_request: int = settings.tg_messages_per_request,
    ) -> None:
        self._tg_client = tg_client
        self._posts_repository = posts_repository
        self._posts_details_tg_repository = posts_details_tg_repository
        self._chats_repository = chats_repository
        self._stream_service = stream_service
        self._output_stream = output_stream
        self._messages_per_request = messages_per_request

    async def process_chat(
        self,
        session,
        chat: ChatTG,
    ) -> None:

        messages = await self._tg_client.get_new_messages(
            entity=chat.chat_id,
            last_seen_message_id=chat.last_seen_message_id,
            limit=self._messages_per_request,
        )

        logger.info(
            "TG chat %s: %d message(s) fetched",
            chat.chat_id,
            len(messages),
        )

        for message in sorted(messages, key=_get_message_sort_id):
            await self._handle_message(
                session=session,
                chat=chat,
                message=message,
            )

    async def _handle_message(
        self,
        session,
        chat: ChatTG,
        message: Any,
    ) -> None:

        message_id = int(message.id)

        try:
            domain_post = await self._persist_message(
                session=session,
                chat=chat,
                message=message,
                message_id=message_id,
            )
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception(
                "Failed to persist TG message %s in chat %s",
                message_id,
                chat.chat_id,
            )
            return

        if domain_post is None:
            return

        # Публикация в Redis после commit БД (тот же компромисс, что в VK).
        try:
            await self._stream_service.publish_post(
                stream=self._output_stream,
                post=domain_post,
            )
        except Exception:
            logger.exception(
                "TG message %s saved but failed to publish to stream '%s'",
                domain_post.id,
                self._output_stream,
            )

    async def _persist_message(
        self,
        session,
        chat: ChatTG,
        message: Any,
        message_id: int,
    ) -> DomainPost | None:

        if not is_processable_message(message):
            await self._mark_seen(session, chat, message_id)
            return None

        is_source_duplicate = await self._posts_details_tg_repository.exists_tg_message(
            session=session,
            chat_id=int(chat.chat_id),
            message_id=message_id,
        )

        if is_source_duplicate:
            await self._mark_seen(session, chat, message_id)
            return None

        text_hash = calculate_text_hash(message.raw_text)

        is_text_duplicate = await self._posts_repository.exists_hash_last_hour(
            session=session,
            text_hash=text_hash,
        )

        if is_text_duplicate:
            await self._mark_seen(session, chat, message_id)
            return None

        mapping = map_tg_message(
            message=message,
            chat=chat,
            text_hash=text_hash,
        )

        created_post = await self._posts_repository.create_post(
            session=session,
            post=mapping.post,
        )

        details = build_post_details_tg(
            mapping=mapping,
            post_id=created_post.id,
        )

        await self._posts_details_tg_repository.create(
            session=session,
            details=details,
        )

        domain_post = build_domain_post(post_model=created_post)

        await self._mark_seen(session, chat, message_id)

        return domain_post

    async def _mark_seen(
        self,
        session,
        chat: ChatTG,
        message_id: int,
    ) -> None:

        await self._chats_repository.update_last_seen_message_id(
            session=session,
            chat_id=chat.chat_id,
            last_seen_message_id=message_id,
        )

        chat.last_seen_message_id = message_id


def _get_message_sort_id(
    message: Any,
) -> int:

    return int(message.id)
