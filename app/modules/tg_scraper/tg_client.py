import logging
from typing import Any

from telethon import TelegramClient

from app.core.config import settings


logger = logging.getLogger(__name__)


class TGClient:

    def __init__(
        self,
        session_name: str = settings.tg_session_name,
        api_id: int = settings.tg_api_id,
        api_hash: str = settings.tg_api_hash,
        flood_sleep_threshold: int = settings.tg_flood_sleep_threshold,
    ) -> None:
        self._client = TelegramClient(session_name, api_id, api_hash)
        self._client.flood_sleep_threshold = flood_sleep_threshold

    @property
    def client(self) -> TelegramClient:
        return self._client

    async def connect(self) -> None:
        await self._client.connect()

    async def is_authorized(self) -> bool:
        return await self._client.is_user_authorized()

    async def warm_entity_cache(self) -> None:

        await self._client.get_dialogs()

    async def disconnect(self) -> None:
        await self._client.disconnect()

    async def get_new_messages(
        self,
        entity: Any,
        last_seen_message_id: int | None,
        limit: int,
    ) -> list[Any]:

        if last_seen_message_id is None:
            kwargs: dict[str, Any] = {"limit": limit}
        else:
            kwargs = {
                "min_id": last_seen_message_id,
                "limit": limit,
                "reverse": True,
            }

        messages: list[Any] = []

        async for message in self._client.iter_messages(entity, **kwargs):
            messages.append(message)

        return messages
