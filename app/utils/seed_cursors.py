import argparse
import asyncio
import logging

from app.core.logging import setup_logging
from app.db.database import SessionLocal
from app.modules.tg_scraper.tg_client import TGClient
from app.modules.vk_scraper.mapper import get_vk_post_id
from app.modules.vk_scraper.vk_client import VKAccessDeniedError
from app.modules.vk_scraper.vk_client import VKClient
from app.repositories.chats_repository import ChatsRepository
from app.repositories.groups_repository import GroupsRepository


logger = logging.getLogger(__name__)


async def seed_vk(only_null: bool) -> None:
    vk_client = VKClient()
    groups_repository = GroupsRepository()

    async with SessionLocal() as session:
        groups = await groups_repository.get_active_groups(session=session)

    for group in groups:
        if only_null and group.last_seen_post_id is not None:
            continue
        try:
            page = await vk_client.get_latest_posts(owner_id=int(group.group_id), count=50, offset=0)
        except VKAccessDeniedError:
            logger.warning("VK %s закрыт — пропуск", group.group_id)
            continue
        except Exception:
            logger.exception("VK %s — ошибка при сидинге", group.group_id)
            continue

        if not page:
            continue

        latest = max(get_vk_post_id(p) for p in page)
        async with SessionLocal() as session:
            await groups_repository.update_last_seen_post_id(
                session=session, group_id=group.group_id, last_seen_post_id=latest
            )
            await session.commit()
        logger.info("VK %s: last_seen_post_id -> %s", group.group_id, latest)


async def seed_tg(only_null: bool) -> None:
    chats_repository = ChatsRepository()

    async with SessionLocal() as session:
        chats = await chats_repository.get_active_chats(session=session)

    tg_client = TGClient()
    await tg_client.connect()
    if not await tg_client.is_authorized():
        logger.error("Telegram-сессия не авторизована. Запусти: python -m app.workers.tg_login")
        await tg_client.disconnect()
        return
    await tg_client.warm_entity_cache()

    try:
        for chat in chats:
            if only_null and chat.last_seen_message_id is not None:
                continue
            try:
                messages = await tg_client.client.get_messages(int(chat.chat_id), limit=1)
            except Exception:
                logger.exception("TG %s — ошибка при сидинге", chat.chat_id)
                continue

            if not messages:
                continue

            latest = int(messages[0].id)
            async with SessionLocal() as session:
                await chats_repository.update_last_seen_message_id(
                    session=session, chat_id=chat.chat_id, last_seen_message_id=latest
                )
                await session.commit()
            logger.info("TG %s: last_seen_message_id -> %s", chat.chat_id, latest)
    finally:
        await tg_client.disconnect()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Seed last_seen cursors to the current latest.")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Сидить все активные источники (по умолчанию — только с пустым курсором)",
    )
    parser.add_argument("--skip-vk", action="store_true")
    parser.add_argument("--skip-tg", action="store_true")
    args = parser.parse_args()

    setup_logging()
    only_null = not args.all

    if not args.skip_vk:
        await seed_vk(only_null=only_null)
    if not args.skip_tg:
        await seed_tg(only_null=only_null)

    logger.info("Сидинг курсоров завершён (only_null=%s)", only_null)


if __name__ == "__main__":
    asyncio.run(main())
