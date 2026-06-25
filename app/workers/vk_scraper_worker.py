import asyncio
import logging

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.redis import redis_client
from app.db.database import SessionLocal
from app.modules.vk_scraper.scraper import VKScraper
from app.modules.vk_scraper.vk_client import VKAccessDeniedError
from app.modules.vk_scraper.vk_client import VKClient
from app.repositories.attachments_repository import AttachmentsRepository
from app.repositories.groups_repository import GroupsRepository
from app.repositories.posts_details_vk_repository import PostsDetailsVKRepository
from app.repositories.posts_repository import PostsRepository
from app.services.stream_service import StreamService


logger = logging.getLogger(__name__)


def build_scraper() -> VKScraper:
    return VKScraper(
        vk_client=VKClient(),
        posts_repository=PostsRepository(),
        posts_details_vk_repository=PostsDetailsVKRepository(),
        attachments_repository=AttachmentsRepository(),
        groups_repository=GroupsRepository(),
        stream_service=StreamService(redis_client=redis_client),
    )


async def run_once(
    scraper: VKScraper,
    groups_repository: GroupsRepository,
) -> None:

    async with SessionLocal() as session:
        groups = await groups_repository.get_active_groups(session=session)

    logger.info("Active VK groups to scrape: %d", len(groups))

    for group in groups:
        try:
            async with SessionLocal() as session:
                await scraper.process_group(
                    session=session,
                    group=group,
                )
        except VKAccessDeniedError as error:
            logger.warning(
                "VK group %s wall is closed (error_code %s: %s), deactivating",
                group.group_id,
                error.error_code,
                error.error_msg,
            )
            async with SessionLocal() as session:
                await groups_repository.deactivate(
                    session=session,
                    group_id=group.group_id,
                )
                await session.commit()
        except Exception:
            logger.exception(
                "Failed to scrape VK group %s",
                group.group_id,
            )


async def main() -> None:
    setup_logging()

    scraper = build_scraper()
    groups_repository = GroupsRepository()

    logger.info(
        "VK scraper worker started, poll interval %ds",
        settings.vk_poll_interval,
    )

    try:
        while True:
            await run_once(
                scraper=scraper,
                groups_repository=groups_repository,
            )
            await asyncio.sleep(settings.vk_poll_interval)
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("VK scraper worker stopping")
    finally:
        await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
