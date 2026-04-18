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
        user_token: str = settings.vk_publish_user_token,
        timeout: float = 30.0,
    ) -> None:
        if not token or not group_id:
            raise RuntimeError("VK_PUBLISH_TOKEN / VK_PUBLISH_GROUP_ID не заданы — заполни .env")

        self._token = token
        # Фото на стену сообщества грузятся только пользовательским токеном.
        self._photo_token = user_token or token
        self._can_upload_photo = bool(user_token)
        self._group_id = int(group_id)
        self._timeout = timeout

    async def publish(self, message: str, photo_urls: list[str]) -> None:
        attachments: list[str] = []
        if photo_urls and not self._can_upload_photo:
            logger.warning(
                "VK: VK_PUBLISH_USER_TOKEN не задан — пост опубликован без фото (%d шт.)",
                len(photo_urls),
            )
        elif self._can_upload_photo:
            for url in photo_urls:
                try:
                    attachments.append(await self._upload_photo(url))
                except Exception as error:
                    # Логируем конкретную причину (права токена или истёкший URL).
                    logger.warning("VK: фото не прикреплено (%s): %s", url, error)

        params = {
            "owner_id": -self._group_id,
            "from_group": 1,
            "message": message,
        }
        # Если фото залиты пользовательским токеном — постим тем же токеном,
        # иначе VK молча отбрасывает вложение, загруженное «другим» токеном.
        post_token = self._token
        if attachments:
            params["attachments"] = ",".join(attachments)
            post_token = self._photo_token
            logger.info("VK: прикрепляю вложения: %s", params["attachments"])

        await self._api("wall.post", params, token=post_token)

    async def _upload_photo(self, url: str) -> str:
        async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as client:
            image = await client.get(url)
            image.raise_for_status()
            image_bytes = image.content

        # Сервер загрузки VK периодически отвечает 5xx/пустым телом — повторяем.
        result: dict | None = None
        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                upload = await self._api(
                    "photos.getWallUploadServer", {"group_id": self._group_id}, token=self._photo_token
                )
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    uploaded = await client.post(
                        upload["upload_url"],
                        files={"photo": ("photo.jpg", image_bytes, "image/jpeg")},
                    )
                uploaded.raise_for_status()
                result = uploaded.json()
                if result.get("photo") and result.get("photo") != "[]":
                    break
                last_error = RuntimeError(f"VK upload вернул пустое фото: {result}")
            except Exception as error:  # noqa: BLE001 — ретраим любые сетевые/5xx сбои
                last_error = error
            logger.warning("VK: загрузка фото, попытка %d не удалась: %s", attempt, last_error)
            result = None

        if not result:
            raise RuntimeError(f"VK upload не удался после 3 попыток: {last_error}")

        saved = await self._api(
            "photos.saveWallPhoto",
            {
                "group_id": self._group_id,
                "server": result["server"],
                "photo": result["photo"],
                "hash": result["hash"],
            },
            token=self._photo_token,
        )
        item = saved[0]
        logger.info("VK: фото сохранено owner_id=%s id=%s", item["owner_id"], item["id"])
        return f"photo{item['owner_id']}_{item['id']}"

    async def _api(self, method: str, params: dict, token: str | None = None) -> dict:
        params = {**params, "access_token": token or self._token, "v": VK_API_VERSION}

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(f"{self.BASE_URL}/{method}", data=params)

        response.raise_for_status()
        data = response.json()

        if "error" in data:
            raise RuntimeError(data["error"])

        return data["response"]
