import json
import logging
import random

import httpx

from app.core.config import settings
from app.modules.bots.keyboards import Keyboard
from app.modules.vk_scraper.settings import VK_API_VERSION


logger = logging.getLogger(__name__)

VK_TEXT_LIMIT = 4096

_COLOR_MAP = {
    "green": "positive",
    "blue": "primary",
    "red": "negative",
    "default": "secondary",
}


def to_vk_keyboard(keyboard: Keyboard | None) -> dict | None:
    if keyboard is None:
        return None
    buttons = [
        [
            {
                "action": {
                    "type": "callback",
                    "label": btn.label,
                    "payload": json.dumps({"d": btn.data}),
                },
                "color": _COLOR_MAP.get(btn.color, "secondary"),
            }
            for btn in row
        ]
        for row in keyboard
    ]
    return {"inline": True, "buttons": buttons}


class VKBotClient:

    BASE_URL = "https://api.vk.com/method"

    def __init__(
        self,
        token: str = settings.vk_publish_token,
        group_id: int = settings.vk_publish_group_id,
        timeout: float = 30.0,
    ) -> None:
        if not token or not group_id:
            raise RuntimeError("VK_PUBLISH_TOKEN / VK_PUBLISH_GROUP_ID не заданы — заполни .env")
        self._token = token
        self._group_id = int(group_id)
        self._timeout = timeout

    async def _api(self, method: str, params: dict) -> dict:
        params = {**params, "access_token": self._token, "v": VK_API_VERSION}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(f"{self.BASE_URL}/{method}", data=params)
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            raise RuntimeError(data["error"])
        return data["response"]

    async def get_long_poll_server(self) -> tuple[str, str, str]:
        r = await self._api("groups.getLongPollServer", {"group_id": self._group_id})
        return r["server"], r["key"], r["ts"]

    async def poll(self, server: str, key: str, ts: str, wait: int = 25) -> dict:
        async with httpx.AsyncClient(timeout=self._timeout + wait) as client:
            response = await client.get(
                server, params={"act": "a_check", "key": key, "ts": ts, "wait": wait}
            )
        response.raise_for_status()
        return response.json()

    async def send_message(self, user_id: int, text: str, keyboard: Keyboard | None = None) -> None:
        params = {
            "user_id": user_id,
            "message": text[:VK_TEXT_LIMIT],
            "random_id": random.randint(1, 2**31 - 1),
        }
        vk_kb = to_vk_keyboard(keyboard)
        if vk_kb is not None:
            params["keyboard"] = json.dumps(vk_kb, ensure_ascii=False)
        else:
            params["keyboard"] = json.dumps({"buttons": [], "one_time": True})
        await self._api("messages.send", params)

    async def edit_message(
        self, peer_id: int, conversation_message_id: int, text: str, keyboard: Keyboard | None = None
    ) -> None:
        params = {
            "peer_id": peer_id,
            "conversation_message_id": conversation_message_id,
            "message": text[:VK_TEXT_LIMIT],
        }
        vk_kb = to_vk_keyboard(keyboard)
        if vk_kb is not None:
            params["keyboard"] = json.dumps(vk_kb, ensure_ascii=False)
        await self._api("messages.edit", params)

    async def send_event_answer(self, event_id: str, user_id: int, peer_id: int) -> None:
        await self._api(
            "messages.sendMessageEventAnswer",
            {"event_id": event_id, "user_id": user_id, "peer_id": peer_id},
        )

    async def send_post(self, user_id: int, text: str, photo_urls: list[str]) -> None:
        attachments: list[str] = []
        for url in photo_urls[:10]:
            try:
                attachments.append(await self._upload_message_photo(user_id, url))
            except Exception:
                logger.warning("VK bot: не удалось приложить фото %s", url, exc_info=True)

        params = {
            "user_id": user_id,
            "message": text[:VK_TEXT_LIMIT],
            "random_id": random.randint(1, 2**31 - 1),
        }
        if attachments:
            params["attachment"] = ",".join(attachments)
        await self._api("messages.send", params)

    async def _upload_message_photo(self, user_id: int, url: str) -> str:
        upload = await self._api("photos.getMessagesUploadServer", {"peer_id": user_id})
        upload_url = upload["upload_url"]

        async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as client:
            image = await client.get(url)
            image.raise_for_status()
            uploaded = await client.post(
                upload_url, files={"photo": ("photo.jpg", image.content, "image/jpeg")}
            )
        result = uploaded.json()

        saved = await self._api(
            "photos.saveMessagesPhoto",
            {"photo": result["photo"], "server": result["server"], "hash": result["hash"]},
        )
        item = saved[0]
        return f"photo{item['owner_id']}_{item['id']}"
