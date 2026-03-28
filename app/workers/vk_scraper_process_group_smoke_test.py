import asyncio

from app.models.groups_vk import GroupVK
from app.modules.vk_scraper.scraper import VKScraper


class FakeVKClient:

    async def get_latest_posts(
        self,
        owner_id: int,
        count: int = 20,
        offset: int = 0,
    ) -> list[dict]:

        print("VK CLIENT OWNER ID:", owner_id, "OFFSET:", offset)

        if offset > 0:
            return []

        return [
            {
                "id": 777,
                "owner_id": owner_id,
                "from_id": owner_id,
                "date": 1_780_000_000,
                "text": "Need one person to carry boxes. Payment 2000 rub.",
                "marked_as_ads": 0,
                "attachments": [
                    {
                        "type": "photo",
                        "photo": {
                            "sizes": [
                                {
                                    "width": 75,
                                    "height": 75,
                                    "url": "https://example.com/small.jpg",
                                },
                                {
                                    "width": 604,
                                    "height": 403,
                                    "url": "https://example.com/large.jpg",
                                },
                            ]
                        },
                    }
                ],
            }
        ]


class FakePostsRepository:

    def __init__(self) -> None:
        self.created_posts = []

    async def exists_hash_last_hour(
        self,
        session,
        text_hash: str,
    ) -> bool:

        print("TEXT HASH:", text_hash)

        return False

    async def create_post(
        self,
        session,
        post,
    ):

        post.id = 100
        self.created_posts.append(post)

        return post


class FakePostsDetailsVKRepository:

    def __init__(self) -> None:
        self.created_details = []

    async def exists_vk_post(
        self,
        session,
        owner_id: int,
        vk_post_id: int,
    ) -> bool:

        print("SOURCE IDS:", owner_id, vk_post_id)

        return False

    async def create(
        self,
        session,
        details,
    ):

        self.created_details.append(details)

        return details


class FakeAttachmentsRepository:

    def __init__(self) -> None:
        self.created_attachments = []

    async def create_many(
        self,
        session,
        attachments: list,
    ) -> None:

        self.created_attachments.extend(attachments)


class FakeGroupsRepository:

    def __init__(self) -> None:
        self.last_seen_updates = []

    async def update_last_seen_post_id(
        self,
        session,
        group_id: int,
        last_seen_post_id: int,
    ) -> None:

        self.last_seen_updates.append(
            (
                group_id,
                last_seen_post_id,
            )
        )


class FakeSession:

    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass


class FakeStreamService:

    def __init__(self) -> None:
        self.published_posts = []

    async def publish_post(
        self,
        stream: str,
        post,
    ) -> str:

        self.published_posts.append(
            (
                stream,
                post,
            )
        )

        return "fake-message-id"


async def main() -> None:
    posts_repository = FakePostsRepository()
    posts_details_repository = FakePostsDetailsVKRepository()
    attachments_repository = FakeAttachmentsRepository()
    groups_repository = FakeGroupsRepository()
    stream_service = FakeStreamService()

    scraper = VKScraper(
        vk_client=FakeVKClient(),
        posts_repository=posts_repository,
        posts_details_vk_repository=posts_details_repository,
        attachments_repository=attachments_repository,
        groups_repository=groups_repository,
        stream_service=stream_service,
    )

    group = GroupVK(
        group_id=-123456,
        title="Test VK group",
        url="https://vk.com/test_group",
        is_active=True,
        last_seen_post_id=None,
    )

    await scraper.process_group(
        session=FakeSession(),
        group=group,
    )

    print("CREATED POSTS:", len(posts_repository.created_posts))
    print("CREATED DETAILS:", len(posts_details_repository.created_details))
    print("CREATED ATTACHMENTS:", len(attachments_repository.created_attachments))
    print("PUBLISHED POSTS:", len(stream_service.published_posts))
    print("LAST SEEN UPDATES:", groups_repository.last_seen_updates)
    print("GROUP LAST SEEN:", group.last_seen_post_id)

    if stream_service.published_posts:
        stream, post = stream_service.published_posts[0]
        print("PUBLISHED STREAM:", stream)
        print("PUBLISHED POST:", post)


if __name__ == "__main__":
    asyncio.run(main())
