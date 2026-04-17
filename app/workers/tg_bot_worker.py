import asyncio
import logging

from aiogram import Bot
from aiogram import Dispatcher
from aiogram.types import InputMediaPhoto
from aiogram.types import KeyboardButton
from aiogram.types import Message
from aiogram.types import ReplyKeyboardMarkup

from app.constants.streams import PREPARED_POSTS_STREAM
from app.constants.streams import TG_BOT_DISPATCHER_GROUP
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.redis import redis_client
from app.db.database import SessionLocal
from app.modules.bots import texts
from app.modules.bots.conversation import process
from app.modules.bots.filters import matches
from app.modules.bots.keyboards import Keyboard
from app.modules.bots.keyboards import MENU_ONLY_KB
from app.models.bot_users import TGBotUser
from app.repositories.bot_users_repository import BotUsersRepository
from app.services.post_formatter import format_post
from app.services.stream_service import StreamService


logger = logging.getLogger(__name__)

CONSUMER_NAME = "tg_bot_dispatcher_1"
TG_TEXT_LIMIT = 4096

dp = Dispatcher()


def _to_tg_keyboard(keyboard: Keyboard | None) -> ReplyKeyboardMarkup | None:
    if keyboard is None:
        return None
    rows = [[KeyboardButton(text=b.label) for b in row] for row in keyboard]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


@dp.message()
async def on_message(message: Message) -> None:
    if message.from_user is None:
        return

    external_id = message.from_user.id
    repo = BotUsersRepository(TGBotUser)

    async with SessionLocal() as session:
        user = await repo.get_by_external_id(session, external_id)
        is_new = user is None
        if is_new:
            user = TGBotUser(external_id=external_id, status="active")
            await repo.add(session, user)

        out_messages = process(user, message.text or "", is_new)
        await session.commit()

    for out in out_messages:
        await message.answer(out.text, reply_markup=_to_tg_keyboard(out.keyboard))


async def _send_post(bot: Bot, chat_id: int, text: str, photo_urls: list[str]) -> None:
    await bot.send_message(chat_id, text[:TG_TEXT_LIMIT], disable_web_page_preview=True)
    if not photo_urls:
        return
    urls = photo_urls[:10]
    if len(urls) == 1:
        await bot.send_photo(chat_id, urls[0])
    else:
        await bot.send_media_group(chat_id, [InputMediaPhoto(media=u) for u in urls])


async def _dispatch(bot: Bot, stream_service: StreamService, repo, message) -> None:
    post = message.post
    try:
        async with SessionLocal() as session:
            users = await repo.list_active(session)

        body = format_post(post, header=texts.POST_HEADER)

        for user in users:
            if not matches(user, post):
                continue
            try:
                await _send_post(bot, user.external_id, body, post.attachments)
            except Exception:
                # Пользователь заблокировал бота и т.п. — не валим рассылку.
                logger.warning("TG bot: не доставлено пользователю %s", user.external_id, exc_info=True)
            await asyncio.sleep(0.05)

        await stream_service.ack(
            stream=PREPARED_POSTS_STREAM, group=TG_BOT_DISPATCHER_GROUP, message_id=message.message_id
        )
    except Exception:
        logger.exception("TG bot dispatch failed for post id=%s", post.id)


async def dispatch_loop(bot: Bot) -> None:
    stream_service = StreamService(redis_client=redis_client)
    repo = BotUsersRepository(TGBotUser)
    logger.info("TG bot dispatcher reading '%s'", PREPARED_POSTS_STREAM)

    while True:
        for message in await stream_service.claim_stale_posts(
            PREPARED_POSTS_STREAM, TG_BOT_DISPATCHER_GROUP, CONSUMER_NAME
        ):
            await _dispatch(bot, stream_service, repo, message)

        for message in await stream_service.read_posts(
            PREPARED_POSTS_STREAM, TG_BOT_DISPATCHER_GROUP, CONSUMER_NAME
        ):
            await _dispatch(bot, stream_service, repo, message)


async def main() -> None:
    setup_logging()

    if not settings.tg_bot_dispatch_token:
        logger.error("TG_BOT_DISPATCH_TOKEN не задан — заполни .env")
        return

    bot = Bot(token=settings.tg_bot_dispatch_token)
    logger.info("TG bot worker started")

    try:
        await asyncio.gather(dp.start_polling(bot), dispatch_loop(bot))
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("TG bot worker stopping")
    finally:
        await bot.session.close()
        await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
