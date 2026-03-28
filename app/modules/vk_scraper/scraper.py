import logging
from typing import Any

from app.constants.streams import NEW_POSTS_STREAM
from app.core.config import settings
from app.domain.post import Post as DomainPost
from app.models.groups_vk import GroupVK
from app.modules.vk_scraper.mapper import build_attachment_models
from app.modules.vk_scraper.mapper import build_domain_post
from app.modules.vk_scraper.mapper import build_post_details_vk
from app.modules.vk_scraper.mapper import get_owner_id
from app.modules.vk_scraper.mapper import get_vk_post_id
from app.modules.vk_scraper.mapper import map_vk_post
from app.modules.vk_scraper.vk_client import VKClient
from app.repositories.attachments_repository import AttachmentsRepository
from app.repositories.groups_repository import GroupsRepository
from app.repositories.posts_details_vk_repository import PostsDetailsVKRepository
from app.repositories.posts_repository import PostsRepository
from app.services.hash_service import calculate_text_hash
from app.services.stream_service import StreamService


logger = logging.getLogger(__name__)


# Предохранитель от бесконечной пагинации по стене сообщества.
MAX_WALL_OFFSET = 1000


class VKScraper:

    def __init__(
        self,
        vk_client: VKClient,
        posts_repository: PostsRepository,
        posts_details_vk_repository: PostsDetailsVKRepository,
        attachments_repository: AttachmentsRepository,
        groups_repository: GroupsRepository,
        stream_service: StreamService,
        output_stream: str = NEW_POSTS_STREAM,
        posts_per_request: int = settings.vk_posts_per_request,
        max_offset: int = MAX_WALL_OFFSET,
    ) -> None:
        self._vk_client = vk_client
        self._posts_repository = posts_repository
        self._posts_details_vk_repository = posts_details_vk_repository
        self._attachments_repository = attachments_repository
        self._groups_repository = groups_repository
        self._stream_service = stream_service
        self._output_stream = output_stream
        self._posts_per_request = posts_per_request
        self._max_offset = max_offset

    async def process_group(
        self,
        session,
        group: GroupVK,
    ) -> None:

        raw_posts = await self._collect_new_posts(group=group)

        logger.info(
            "VK group %s: %d new post(s) to process",
            group.group_id,
            len(raw_posts),
        )

        for raw_post in sorted(raw_posts, key=_get_vk_post_sort_id):
            await self._handle_post(
                session=session,
                group=group,
                raw_post=raw_post,
            )

    async def _collect_new_posts(
        self,
        group: GroupVK,
    ) -> list[dict[str, Any]]:
        """
        Постранично собирает посты, появившиеся после last_seen_post_id.

        VK возвращает посты в порядке от новых к старым, поэтому пагинация
        идёт по offset до тех пор, пока не встретится уже виденный пост.
        На самом первом проходе (last_seen_post_id is None) забирается только
        первая страница, чтобы не тянуть всю историю стены.
        """

        owner_id = int(group.group_id)
        last_seen = group.last_seen_post_id

        collected: list[dict[str, Any]] = []
        offset = 0

        while True:
            page = await self._vk_client.get_latest_posts(
                owner_id=owner_id,
                count=self._posts_per_request,
                offset=offset,
            )

            if not page:
                break

            reached_seen = False

            for raw_post in page:
                vk_post_id = get_vk_post_id(raw_post)

                # Закреплённые посты всегда идут первыми и могут быть старыми,
                # поэтому по ним нельзя останавливать пагинацию.
                if raw_post.get("is_pinned"):
                    if last_seen is None or vk_post_id > last_seen:
                        collected.append(raw_post)
                    continue

                if last_seen is not None and vk_post_id <= last_seen:
                    reached_seen = True
                    break

                collected.append(raw_post)

            if reached_seen or last_seen is None:
                break

            offset += len(page)

            if offset >= self._max_offset:
                logger.warning(
                    "VK group %s: reached max offset %d, stopping pagination",
                    group.group_id,
                    self._max_offset,
                )
                break

        return collected

    async def _handle_post(
        self,
        session,
        group: GroupVK,
        raw_post: dict[str, Any],
    ) -> None:

        vk_post_id = get_vk_post_id(raw_post)

        try:
            domain_post = await self._persist_post(
                session=session,
                group=group,
                raw_post=raw_post,
                vk_post_id=vk_post_id,
            )
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception(
                "Failed to persist VK post %s in group %s",
                vk_post_id,
                group.group_id,
            )
            return

        if domain_post is None:
            return

        # Публикация в Redis намеренно делается после commit БД.
        # Если она упадёт, пост уже сохранён и не будет переотправлен
        # (last_seen_post_id сдвинут) — это редкий и осознанный риск MVP.
        try:
            await self._stream_service.publish_post(
                stream=self._output_stream,
                post=domain_post,
            )
        except Exception:
            logger.exception(
                "VK post %s saved but failed to publish to stream '%s'",
                domain_post.id,
                self._output_stream,
            )

    async def _persist_post(
        self,
        session,
        group: GroupVK,
        raw_post: dict[str, Any],
        vk_post_id: int,
    ) -> DomainPost | None:
        """
        Сохраняет подходящий пост в БД и возвращает доменный объект.

        Отфильтрованные посты (без текста, реклама, дубли) не сохраняются,
        но last_seen_post_id для них всё равно сдвигается, чтобы не
        переобрабатывать их на следующем проходе. Возвращает None.
        """

        if not raw_post.get("text"):
            await self._mark_post_seen(session, group, vk_post_id)
            return None

        if raw_post.get("marked_as_ads") == 1:
            await self._mark_post_seen(session, group, vk_post_id)
            return None

        owner_id = get_owner_id(vk_post=raw_post, group=group)

        is_source_duplicate = await self._posts_details_vk_repository.exists_vk_post(
            session=session,
            owner_id=owner_id,
            vk_post_id=vk_post_id,
        )

        if is_source_duplicate:
            await self._mark_post_seen(session, group, vk_post_id)
            return None

        text_hash = calculate_text_hash(raw_post["text"])

        is_text_duplicate = await self._posts_repository.exists_hash_last_hour(
            session=session,
            text_hash=text_hash,
        )

        if is_text_duplicate:
            await self._mark_post_seen(session, group, vk_post_id)
            return None

        mapping = map_vk_post(
            vk_post=raw_post,
            group=group,
            text_hash=text_hash,
        )

        created_post = await self._posts_repository.create_post(
            session=session,
            post=mapping.post,
        )

        details = build_post_details_vk(
            mapping=mapping,
            post_id=created_post.id,
        )

        await self._posts_details_vk_repository.create(
            session=session,
            details=details,
        )

        attachments = build_attachment_models(
            post_id=created_post.id,
            attachment_urls=mapping.attachment_urls,
        )

        if attachments:
            await self._attachments_repository.create_many(
                session=session,
                attachments=attachments,
            )

        domain_post = build_domain_post(
            post_model=created_post,
            attachment_urls=mapping.attachment_urls,
        )

        await self._mark_post_seen(session, group, vk_post_id)

        return domain_post

    async def _mark_post_seen(
        self,
        session,
        group: GroupVK,
        vk_post_id: int,
    ) -> None:

        await self._groups_repository.update_last_seen_post_id(
            session=session,
            group_id=group.group_id,
            last_seen_post_id=vk_post_id,
        )

        group.last_seen_post_id = vk_post_id


def _get_vk_post_sort_id(
    raw_post: dict[str, Any],
) -> int:

    return int(raw_post["id"])
