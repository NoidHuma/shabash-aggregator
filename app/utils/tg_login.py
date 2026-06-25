import asyncio
import logging

from telethon import TelegramClient

from app.core.config import settings
from app.core.logging import setup_logging


logger = logging.getLogger(__name__)


async def main() -> None:

    setup_logging()

    client = TelegramClient(
        settings.tg_session_name,
        settings.tg_api_id,
        settings.tg_api_hash,
    )

    await client.start()

    me = await client.get_me()

    logger.info(
        "Authorized as %s (id=%s, username=@%s). Session file: %s.session",
        me.first_name,
        me.id,
        me.username,
        settings.tg_session_name,
    )

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
