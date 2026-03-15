from app.modules.vk_scraper.vk_client import VKClient


class VKScraper:

    def __init__(
        self,
        vk_client: VKClient,
    ) -> None:
        self._vk_client = vk_client

    async def process_group(
        self,
        owner_id: int,
    ) -> None:

        posts = await self._vk_client.get_latest_posts(
            owner_id=owner_id,
        )

        for post in posts:

            text = post.get("text")

            if not text:
                continue