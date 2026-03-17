from app.modules.vk_scraper.vk_client import VKClient
from app.repositories.posts_repository import PostsRepository
from app.services.hash_service import calculate_text_hash


class VKScraper:

    def __init__(
            self,
            vk_client: VKClient,
            posts_repository: PostsRepository,
    ) -> None:
        self._vk_client = vk_client
        self._posts_repository = posts_repository

    async def process_group(
            self,
            session,
            owner_id: int,
    ) -> None:

        posts = await self._vk_client.get_latest_posts(
            owner_id=owner_id,
        )

        for post in posts:

            text = post.get("text")

            if not text:
                continue

            if post.get("marked_as_ads") == 1:
                continue

            text_hash = calculate_text_hash(text)

            is_duplicate = (
                await self._posts_repository.exists_hash_last_hour(
                    session=session,
                    text_hash=text_hash,
                )
            )

            if is_duplicate:
                continue