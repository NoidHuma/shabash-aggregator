import asyncio
import json
import logging

import httpx

from app.core.config import settings


logger = logging.getLogger(__name__)


TG_TEXT_LIMIT = 4096
TG_MAX_MEDIA = 10


class TGPublisherClient:

    def __init__(
        self,
        bot_token: str = settings.tg_bot_token,
        chat_id: str = settings.tg_channel,
        timeout: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        if not bot_token or not chat_id:
            raise RuntimeError("TG_BOT_TOKEN / TG_CHANNEL не заданы — заполни .env")

        self._base_url = f"https://api.telegram.org/bot{bot_token}"
        self._chat_id = chat_id
        self._timeout = timeout
        self._max_retries = max_retries

    async def publish(self, text: str, photo_urls: list[str]) -> None:
        sent = await self._send_text(text)
        if photo_urls:
            await self._send_photos(photo_urls, reply_to=sent.get("message_id"))

    async def _send_text(self, text: str) -> dict:
        return await self._call(
            "sendMessage",
            {
                "chat_id": self._chat_id,
                "text": text[:TG_TEXT_LIMIT],
                "disable_web_page_preview": True,
            },
        )

    async def _send_photos(self, photo_urls: list[str], reply_to: int | None = None) -> None:
        urls = photo_urls[:TG_MAX_MEDIA]
        reply = json.dumps({"message_id": reply_to}) if reply_to else None
        if len(urls) == 1:
            data = {"chat_id": self._chat_id, "photo": urls[0]}
            if reply:
                data["reply_parameters"] = reply
            await self._call("sendPhoto", data)
        else:
            data = {"chat_id": self._chat_id, "media": json.dumps([{"type": "photo", "media": url} for url in urls])}
            if reply:
                data["reply_parameters"] = reply
            await self._call("sendMediaGroup", data)

    async def _call(self, method: str, data: dict) -> dict:
        for attempt in range(self._max_retries + 1):
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(f"{self._base_url}/{method}", data=data)

            payload = response.json()
            if payload.get("ok"):
                return payload["result"]

            retry_after = (payload.get("parameters") or {}).get("retry_after")
            if retry_after and attempt < self._max_retries:
                logger.warning("Telegram %s 429, ждём %sс", method, retry_after)
                await asyncio.sleep(float(retry_after) + 0.5)
                continue

            raise RuntimeError(f"Telegram {method} failed: {payload}")

        raise RuntimeError(f"Telegram {method}: исчерпаны повторы")
