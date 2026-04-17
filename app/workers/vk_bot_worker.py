import asyncio
import json
import logging

from app.constants.streams import PREPARED_POSTS_STREAM
from app.constants.streams import VK_BOT_DISPATCHER_GROUP
from app.core.logging import setup_logging
from app.core.redis import redis_client
from app.db.database import SessionLocal
from app.modules.bots import texts
from app.modules.bots.conversation import process
from app.modules.bots.filters import matches
from app.models.bot_users import VKBotUser
from app.modules.vk_bot import VKBotClient
from app.repositories.bot_users_repository import BotUsersRepository
from app.services.post_formatter import format_post
from app.services.stream_service import StreamService


logger = logging.getLogger(__name__)

CONSUMER_NAME = "vk_bot_dispatcher_1"


async def _process_user_input(client: VKBotClient, external_id: int, text: str) -> None:
    repo = BotUsersRepository(VKBotUser)
    async with SessionLocal() as session:
        user = await repo.get_by_external_id(session, external_id)
        is_new = user is None
        if is_new:
            user = VKBotUser(external_id=external_id, status="active")
            await repo.add(session, user)

        out_messages = process(user, text, is_new)
        await session.commit()

    for out in out_messages:
        await client.send_message(external_id, out.text, out.keyboard)


def _is_start_payload(payload) -> bool:
    if not payload:
        return False
    try:
        data = json.loads(payload) if isinstance(payload, str) else payload
    except (ValueError, TypeError):
        return False
    return isinstance(data, dict) and data.get("command") == "start"


async def _handle_update(client: VKBotClient, update: dict) -> None:
    update_type = update.get("type")
    try:
        if update_type == "message_new":
            message = update["object"]["message"]
            from_id = int(message["from_id"])
            if from_id < 0:  # сообщение от сообщества — игнорируем
                return
            text = message.get("text", "")
            # Кнопка «Начать» шлёт payload {"command":"start"}, а не текст.
            if _is_start_payload(message.get("payload")):
                text = "/start"
            await _process_user_input(client, from_id, text)
        elif update_type == "message_allow":
            user_id = int(update["object"]["user_id"])
            await _process_user_input(client, user_id, "/start")
    except Exception:
        logger.exception("VK bot: ошибка обработки апдейта %s", update_type)


async def long_poll_loop(client: VKBotClient) -> None:
    server, key, ts = await client.get_long_poll_server()
    logger.info("VK bot long poll started")

    while True:
        try:
            data = await client.poll(server, key, ts)
        except Exception:
            logger.exception("VK bot poll error, переподключаюсь через 3с")
            await asyncio.sleep(3)
            server, key, ts = await client.get_long_poll_server()
            continue

        failed = data.get("failed")
        if failed:
            if failed == 1:
                ts = data["ts"]
            else:
                server, key, ts = await client.get_long_poll_server()
            continue

        ts = data.get("ts", ts)
        for update in data.get("updates", []):
            await _handle_update(client, update)


async def _dispatch(client: VKBotClient, stream_service: StreamService, repo, message) -> None:
    post = message.post
    try:
        async with SessionLocal() as session:
            users = await repo.list_active(session)

        body = format_post(post, header=texts.POST_HEADER)

        for user in users:
            if not matches(user, post):
                continue
            try:
                await client.send_post(user.external_id, body, post.attachments)
            except Exception:
                logger.warning("VK bot: не доставлено пользователю %s", user.external_id, exc_info=True)
            await asyncio.sleep(0.1)

        await stream_service.ack(
            stream=PREPARED_POSTS_STREAM, group=VK_BOT_DISPATCHER_GROUP, message_id=message.message_id
        )
    except Exception:
        logger.exception("VK bot dispatch failed for post id=%s", post.id)


async def dispatch_loop(client: VKBotClient) -> None:
    stream_service = StreamService(redis_client=redis_client)
    repo = BotUsersRepository(VKBotUser)
    logger.info("VK bot dispatcher reading '%s'", PREPARED_POSTS_STREAM)

    while True:
        for message in await stream_service.claim_stale_posts(
            PREPARED_POSTS_STREAM, VK_BOT_DISPATCHER_GROUP, CONSUMER_NAME
        ):
            await _dispatch(client, stream_service, repo, message)

        for message in await stream_service.read_posts(
            PREPARED_POSTS_STREAM, VK_BOT_DISPATCHER_GROUP, CONSUMER_NAME
        ):
            await _dispatch(client, stream_service, repo, message)


async def main() -> None:
    setup_logging()

    client = VKBotClient()
    logger.info("VK bot worker started")

    try:
        await asyncio.gather(long_poll_loop(client), dispatch_loop(client))
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("VK bot worker stopping")
    finally:
        await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
