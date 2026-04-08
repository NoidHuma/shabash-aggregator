import argparse
import asyncio
import logging

from app.constants.streams import NEW_POSTS_STREAM
from app.core.logging import setup_logging
from app.core.redis import redis_client
from app.db.database import SessionLocal
from app.modules.tg_scraper.mapper import build_domain_post as tg_build_domain_post
from app.modules.tg_scraper.mapper import build_post_details_tg
from app.modules.tg_scraper.mapper import is_processable_message
from app.modules.tg_scraper.mapper import map_tg_message
from app.modules.tg_scraper.tg_client import TGClient
from app.modules.vk_scraper.mapper import build_attachment_models
from app.modules.vk_scraper.mapper import build_domain_post as vk_build_domain_post
from app.modules.vk_scraper.mapper import build_post_details_vk
from app.modules.vk_scraper.mapper import get_owner_id
from app.modules.vk_scraper.mapper import get_vk_post_id
from app.modules.vk_scraper.mapper import map_vk_post
from app.modules.vk_scraper.vk_client import VKAccessDeniedError
from app.modules.vk_scraper.vk_client import VKClient
from app.repositories.attachments_repository import AttachmentsRepository
from app.repositories.chats_repository import ChatsRepository
from app.repositories.groups_repository import GroupsRepository
from app.repositories.posts_details_tg_repository import PostsDetailsTGRepository
from app.repositories.posts_details_vk_repository import PostsDetailsVKRepository
from app.repositories.posts_repository import PostsRepository
from app.services.hash_service import calculate_text_hash
from app.services.stream_service import StreamService


logger = logging.getLogger(__name__)


# Разовый бэкафилл: накопить в таблице posts историю публикаций из активных
# источников для последующего набора ML-датасета.
#
# Поведение повторяет intake сборщиков (тот же дедуп и фильтры), но:
#   - идёт вглубь истории (постранично / iter_messages), а не только свежее;
#   - НЕ трогает last_seen_*_id, чтобы не сбивать инкрементальный опрос;
#   - по умолчанию НЕ публикует в Redis (просто копит в posts).


async def backfill_vk(
    vk_client: VKClient,
    stream_service: StreamService | None,
    target_per_group: int,
    page_size: int,
    max_offset: int,
    publish: bool,
) -> int:

    posts_repository = PostsRepository()
    posts_details_vk_repository = PostsDetailsVKRepository()
    attachments_repository = AttachmentsRepository()
    groups_repository = GroupsRepository()

    async with SessionLocal() as session:
        groups = await groups_repository.get_active_groups(session=session)

    logger.info("VK backfill: %d active group(s), target %d each", len(groups), target_per_group)

    total = 0

    for group in groups:
        owner_id = int(group.group_id)
        inserted = 0
        offset = 0

        try:
            while inserted < target_per_group and offset < max_offset:
                page = await vk_client.get_latest_posts(
                    owner_id=owner_id,
                    count=page_size,
                    offset=offset,
                )

                if not page:
                    break

                for raw_post in page:
                    if inserted >= target_per_group:
                        break

                    domain_post = await _persist_vk_post(
                        raw_post=raw_post,
                        group=group,
                        posts_repository=posts_repository,
                        posts_details_vk_repository=posts_details_vk_repository,
                        attachments_repository=attachments_repository,
                    )

                    if domain_post is None:
                        continue

                    if publish and stream_service is not None:
                        await stream_service.publish_post(
                            stream=NEW_POSTS_STREAM,
                            post=domain_post,
                        )

                    inserted += 1

                offset += len(page)
        except VKAccessDeniedError as error:
            logger.warning("VK group %s skipped (closed wall: %s)", owner_id, error.error_msg)
        except Exception:
            logger.exception("VK group %s failed during backfill", owner_id)

        logger.info("VK group %s: inserted %d", owner_id, inserted)
        total += inserted

    logger.info("VK backfill done: %d posts inserted", total)
    return total


async def _persist_vk_post(
    raw_post,
    group,
    posts_repository,
    posts_details_vk_repository,
    attachments_repository,
):
    """Сохраняет один VK-пост в отдельной транзакции. Возвращает Post или None."""

    if not raw_post.get("text"):
        return None

    if raw_post.get("marked_as_ads") == 1:
        return None

    vk_post_id = get_vk_post_id(raw_post)
    owner_id = get_owner_id(vk_post=raw_post, group=group)

    async with SessionLocal() as session:
        try:
            if await posts_details_vk_repository.exists_vk_post(
                session=session, owner_id=owner_id, vk_post_id=vk_post_id
            ):
                return None

            text_hash = calculate_text_hash(raw_post["text"])

            if await posts_repository.exists_hash_last_hour(session=session, text_hash=text_hash):
                return None

            mapping = map_vk_post(vk_post=raw_post, group=group, text_hash=text_hash)
            created_post = await posts_repository.create_post(session=session, post=mapping.post)

            details = build_post_details_vk(mapping=mapping, post_id=created_post.id)
            await posts_details_vk_repository.create(session=session, details=details)

            attachments = build_attachment_models(
                post_id=created_post.id, attachment_urls=mapping.attachment_urls
            )
            if attachments:
                await attachments_repository.create_many(session=session, attachments=attachments)

            domain_post = vk_build_domain_post(
                post_model=created_post, attachment_urls=mapping.attachment_urls
            )

            await session.commit()
            return domain_post
        except Exception:
            await session.rollback()
            logger.exception("Failed to persist VK post %s", vk_post_id)
            return None


async def backfill_tg(
    tg_client: TGClient,
    stream_service: StreamService | None,
    target_per_chat: int,
    max_scan: int,
    publish: bool,
) -> int:

    posts_repository = PostsRepository()
    posts_details_tg_repository = PostsDetailsTGRepository()
    chats_repository = ChatsRepository()

    async with SessionLocal() as session:
        chats = await chats_repository.get_active_chats(session=session)

    logger.info("TG backfill: %d active chat(s), target %d each", len(chats), target_per_chat)

    total = 0

    for chat in chats:
        chat_id = int(chat.chat_id)
        inserted = 0

        try:
            async for message in tg_client.client.iter_messages(chat_id, limit=max_scan):
                if inserted >= target_per_chat:
                    break

                if not is_processable_message(message):
                    continue

                domain_post = await _persist_tg_message(
                    message=message,
                    chat=chat,
                    posts_repository=posts_repository,
                    posts_details_tg_repository=posts_details_tg_repository,
                )

                if domain_post is None:
                    continue

                if publish and stream_service is not None:
                    await stream_service.publish_post(
                        stream=NEW_POSTS_STREAM,
                        post=domain_post,
                    )

                inserted += 1
        except Exception:
            logger.exception("TG chat %s failed during backfill", chat_id)

        logger.info("TG chat %s: inserted %d", chat_id, inserted)
        total += inserted

    logger.info("TG backfill done: %d posts inserted", total)
    return total


async def _persist_tg_message(
    message,
    chat,
    posts_repository,
    posts_details_tg_repository,
):
    """Сохраняет одно TG-сообщение в отдельной транзакции. Возвращает Post или None."""

    message_id = int(message.id)
    chat_id = int(chat.chat_id)

    async with SessionLocal() as session:
        try:
            if await posts_details_tg_repository.exists_tg_message(
                session=session, chat_id=chat_id, message_id=message_id
            ):
                return None

            text_hash = calculate_text_hash(message.raw_text)

            if await posts_repository.exists_hash_last_hour(session=session, text_hash=text_hash):
                return None

            mapping = map_tg_message(message=message, chat=chat, text_hash=text_hash)
            created_post = await posts_repository.create_post(session=session, post=mapping.post)

            details = build_post_details_tg(mapping=mapping, post_id=created_post.id)
            await posts_details_tg_repository.create(session=session, details=details)

            domain_post = tg_build_domain_post(post_model=created_post)

            await session.commit()
            return domain_post
        except Exception:
            await session.rollback()
            logger.exception("Failed to persist TG message %s in chat %s", message_id, chat_id)
            return None


async def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill posts table for dataset collection.")
    parser.add_argument("--vk-per-group", type=int, default=330)
    parser.add_argument("--tg-per-chat", type=int, default=830)
    parser.add_argument("--vk-page-size", type=int, default=100)
    parser.add_argument("--vk-max-offset", type=int, default=5000)
    parser.add_argument("--tg-max-scan", type=int, default=8000)
    parser.add_argument("--publish", action="store_true", help="Also publish to new_posts stream")
    parser.add_argument("--skip-vk", action="store_true")
    parser.add_argument("--skip-tg", action="store_true")
    args = parser.parse_args()

    setup_logging()

    stream_service = StreamService(redis_client=redis_client) if args.publish else None

    if not args.skip_vk:
        await backfill_vk(
            vk_client=VKClient(),
            stream_service=stream_service,
            target_per_group=args.vk_per_group,
            page_size=args.vk_page_size,
            max_offset=args.vk_max_offset,
            publish=args.publish,
        )

    if not args.skip_tg:
        tg_client = TGClient()
        await tg_client.connect()

        if not await tg_client.is_authorized():
            logger.error("Telegram session not authorized. Run: python -m app.workers.tg_login")
        else:
            await tg_client.warm_entity_cache()
            await backfill_tg(
                tg_client=tg_client,
                stream_service=stream_service,
                target_per_chat=args.tg_per_chat,
                max_scan=args.tg_max_scan,
                publish=args.publish,
            )

        await tg_client.disconnect()

    if args.publish:
        await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
