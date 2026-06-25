import asyncio
import logging

from telethon.errors import FloodWaitError

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.redis import redis_client
from app.db.database import SessionLocal
from app.modules.tg_scraper.scraper import TGScraper
from app.modules.tg_scraper.tg_client import TGClient
from app.repositories.chats_repository import ChatsRepository
from app.repositories.posts_details_tg_repository import PostsDetailsTGRepository
from app.repositories.posts_repository import PostsRepository
from app.services.stream_service import StreamService


logger = logging.getLogger(__name__)


def build_scraper(tg_client: TGClient) -> TGScraper:
    return TGScraper(
        tg_client=tg_client,
        posts_repository=PostsRepository(),
        posts_details_tg_repository=PostsDetailsTGRepository(),
        chats_repository=ChatsRepository(),
        stream_service=StreamService(redis_client=redis_client),
    )


async def run_once(
    scraper: TGScraper,
    chats_repository: ChatsRepository,
) -> None:

    async with SessionLocal() as session:
        chats = await chats_repository.get_active_chats(session=session)

    logger.info("Active TG chats to scrape: %d", len(chats))

    for chat in chats:
        try:
            async with SessionLocal() as session:
                await scraper.process_chat(
                    session=session,
                    chat=chat,
                )
        except FloodWaitError as error:
            logger.warning(
                "FloodWait %ss on TG chat %s, skipping until next cycle",
                error.seconds,
                chat.chat_id,
            )
        except Exception:
            logger.exception(
                "Failed to scrape TG chat %s",
                chat.chat_id,
            )


async def main() -> None:
    setup_logging()

    tg_client = TGClient()
    await tg_client.connect()

    if not await tg_client.is_authorized():
        logger.error(
            "Telegram session is not authorized. "
            "Run once: python -m app.workers.tg_login"
        )
        await tg_client.disconnect()
        return

    await tg_client.warm_entity_cache()

    scraper = build_scraper(tg_client)
    chats_repository = ChatsRepository()

    logger.info(
        "TG scraper worker started, poll interval %ds",
        settings.tg_poll_interval,
    )

    try:
        while True:
            await run_once(
                scraper=scraper,
                chats_repository=chats_repository,
            )
            await asyncio.sleep(settings.tg_poll_interval)
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("TG scraper worker stopping")
    finally:
        await tg_client.disconnect()
        await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
