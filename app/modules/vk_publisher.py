import logging

import httpx

from app.core.config import settings
from app.modules.vk_scraper.settings import VK_API_VERSION


logger = logging.getLogger(__name__)


class VKPublisherClient:
    """
    Публикация в стену VK-сообщества через wall.post.

    Фото нельзя прикрепить чужим URL — каждое перезаливается в наше сообщество
    (getWallUploadServer -> upload -> saveWallPhoto), затем прикрепляется к посту.
    Если фото загрузить не удалось — пост всё равно публикуется (без него).
    """

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

    async def publish(self, message: str, photo_urls: list[str]) -> None:
        attachments: list[str] = []
        for url in photo_urls:
            try:
                attachments.append(await self._upload_photo(url))
            except Exception:
                logger.exception("VK: не удалось перезалить фото %s — пропускаю", url)

        params = {
            "owner_id": -self._group_id,
            "from_group": 1,
            "message": message,
        }
        if attachments:
            params["attachments"] = ",".join(attachments)

        await self._api("wall.post", params)

    async def _upload_photo(self, url: str) -> str:
        upload = await self._api("photos.getWallUploadServer", {"group_id": self._group_id})
        upload_url = upload["upload_url"]

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            image = await client.get(url)
            image.raise_for_status()

            uploaded = await client.post(
                upload_url,
                files={"photo": ("photo.jpg", image.content, "image/jpeg")},
            )
        result = uploaded.json()

        if not result.get("photo") or result.get("photo") == "[]":
            raise RuntimeError(f"VK upload вернул пустое фото: {result}")

        saved = await self._api(
            "photos.saveWallPhoto",
            {
                "group_id": self._group_id,
                "server": result["server"],
                "photo": result["photo"],
                "hash": result["hash"],
            },
        )
        item = saved[0]
        return f"photo{item['owner_id']}_{item['id']}"

    async def _api(self, method: str, params: dict) -> dict:
        params = {**params, "access_token": self._token, "v": VK_API_VERSION}

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(f"{self.BASE_URL}/{method}", data=params)

        response.raise_for_status()
        data = response.json()

        if "error" in data:
            raise RuntimeError(data["error"])

        return data["response"]
