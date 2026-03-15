# app/modules/vk_scraper/vk_client.py

import httpx

from app.core.config import settings
from app.modules.vk_scraper.settings import VK_API_VERSION


class VKClient:
    """
    Клиент для работы с VK API.
    """

    BASE_URL = "https://api.vk.com/method"

    async def get_latest_posts(
        self,
        owner_id: int,
        count: int = 20,
    ) -> list[dict]:
        """
        Получить последние посты сообщества.
        """

        params = {
            "owner_id": owner_id,
            "count": count,
            "access_token": settings.vk_token,
            "v": VK_API_VERSION,
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/wall.get",
                params=params,
            )

        response.raise_for_status()

        data = response.json()

        if "error" in data:
            raise RuntimeError(data["error"])

        return data["response"]["items"]

    async def get_group_info(
        self,
        owner_id: int,
    ) -> dict:
        """
        Будет реализовано позже.
        """

        raise NotImplementedError