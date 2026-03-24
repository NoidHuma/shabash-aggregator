from app.models.groups_vk import GroupVK
from app.modules.vk_scraper.mapper import build_attachment_models
from app.modules.vk_scraper.mapper import build_domain_post
from app.modules.vk_scraper.mapper import build_post_details_vk
from app.modules.vk_scraper.mapper import build_vk_post_url
from app.modules.vk_scraper.mapper import extract_photo_urls
from app.modules.vk_scraper.mapper import map_vk_post


def main() -> None:
    group = GroupVK(
        group_id=123456,
        title="Test VK group",
        url="https://vk.com/test_group",
        is_active=True,
    )

    vk_post = {
        "id": 777,
        "owner_id": -123456,
        "from_id": -123456,
        "date": 1_780_000_000,
        "text": "Need one person to carry boxes. Payment 2000 rub.",
        "attachments": [
            {
                "type": "photo",
                "photo": {
                    "sizes": [
                        {
                            "type": "s",
                            "width": 75,
                            "height": 75,
                            "url": "https://example.com/small.jpg",
                        },
                        {
                            "type": "x",
                            "width": 604,
                            "height": 403,
                            "url": "https://example.com/large.jpg",
                        },
                    ]
                },
            },
            {
                "type": "video",
                "video": {
                    "id": 1,
                },
            },
        ],
    }

    mapping = map_vk_post(
        vk_post=vk_post,
        group=group,
        text_hash="test_hash",
    )

    print("URL:", build_vk_post_url(-123456, 777))
    print("PHOTO URLS:", extract_photo_urls(vk_post))
    print("POST MODEL TEXT:", mapping.post.text)
    print("POST MODEL SOURCE URL:", mapping.post.source_post_url)
    print("POST MODEL CHAT URL:", mapping.post.source_chat_url)
    print("OWNER ID:", mapping.owner_id)
    print("VK POST ID:", mapping.vk_post_id)
    print("FROM ID:", mapping.from_id)
    print("ATTACHMENT URLS:", mapping.attachment_urls)

    mapping.post.id = 10

    details = build_post_details_vk(
        mapping=mapping,
        post_id=mapping.post.id,
    )

    attachments = build_attachment_models(
        post_id=mapping.post.id,
        attachment_urls=mapping.attachment_urls,
    )

    domain_post = build_domain_post(
        post_model=mapping.post,
        attachment_urls=mapping.attachment_urls,
    )

    print("DETAILS:", details.post_id, details.owner_id, details.vk_post_id)
    print("ATTACHMENTS:", [(item.post_id, item.url, item.position) for item in attachments])
    print("DOMAIN POST:", domain_post)


if __name__ == "__main__":
    main()
