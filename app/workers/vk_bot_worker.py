import asyncio
import json
import logging

from app.constants.streams import PREPARED_POSTS_STREAM
from app.constants.streams import VK_BOT_DISPATCHER_GROUP
from app.core.logging import setup_logging
from app.core.redis import redis_client
from app.db.database import SessionLocal
from app.modules.bots import texts
from app.modules.bots.conversation import handle_callback
from app.modules.bots.conversation import handle_command
from app.modules.bots.filters import matches
from app.models.bot_users import VKBotUser
from app.modules.vk_bot import VKBotClient
from app.repositories.bot_users_repository import BotUsersRepository
from app.services.post_formatter import format_post
from app.services.stream_service import StreamService


logger = logging.getLogger(__name__)

CONSUMER_NAME = "vk_bot_dispatcher_1"


async def _get_or_create(session, repo, external_id):
    user = await repo.get_by_external_id(session, external_id)
    is_new = user is None
    if is_new:
        user = VKBotUser(external_id=external_id, status="active")
        await repo.add(session, user)
    return user, is_new


async def _process_command(client: VKBotClient, external_id: int, text: str) -> None:
    repo = BotUsersRepository(VKBotUser)
    async with SessionLocal() as session:
        user, is_new = await _get_or_create(session, repo, external_id)
        outs = handle_command(user, text, is_new)
        await session.commit()
    for out in outs:
        await client.send_message(external_id, out.text, out.keyboard)


async def _process_callback(client: VKBotClient, obj: dict) -> None:
    user_id = int(obj["user_id"])
    peer_id = int(obj["peer_id"])
    event_id = obj["event_id"]
    cmid = obj["conversation_message_id"]
    payload = obj.get("payload") or {}
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except ValueError:
            payload = {}
    data = payload.get("d", "") if isinstance(payload, dict) else ""

    repo = BotUsersRepository(VKBotUser)
    async with SessionLocal() as session:
        user, _ = await _get_or_create(session, repo, user_id)
        out = handle_callback(user, data)
        await session.commit()

    try:
        await client.edit_message(peer_id, cmid, out.text, out.keyboard)
    except Exception:
        logger.warning("VK bot: не удалось отредактировать сообщение", exc_info=True)
    await client.send_event_answer(event_id, user_id, peer_id)


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
            if from_id < 0:
                return
            text = message.get("text", "")
            if _is_start_payload(message.get("payload")):
                text = "/start"
            await _process_command(client, from_id, text)
        elif update_type == "message_allow":
            await _process_command(client, int(update["object"]["user_id"]), "/start")
        elif update_type == "message_event":
            await _process_callback(client, update["object"])
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
