import argparse
import asyncio
import sys

from app.db.database import SessionLocal
from app.modules.attribute_extractor.extractor import LLMExtractor
from app.modules.attribute_extractor.extractor import StubExtractor
from app.modules.attribute_extractor.llm_client import LLMClient
from app.repositories.posts_repository import PostsRepository


async def _fetch_post_text(post_id: int) -> str:
    async with SessionLocal() as session:
        post = await PostsRepository().get_by_id(session=session, post_id=post_id)
    if post is None:
        raise SystemExit(f"Пост id={post_id} не найден")
    return post.text


def main() -> None:
    parser = argparse.ArgumentParser(description="Ручная проверка извлечения атрибутов.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", help="Текст публикации")
    group.add_argument("--post-id", type=int, help="Взять текст из posts по id")
    parser.add_argument("--stub", action="store_true", help="Использовать заглушку вместо LLM")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    text = args.text if args.text is not None else asyncio.run(_fetch_post_text(args.post_id))

    extractor = StubExtractor() if args.stub else LLMExtractor(LLMClient())
    attributes = extractor.extract(text)

    print("=" * 60)
    print(text)
    print("=" * 60)
    print(f"duration : {attributes.duration.value}")
    print(f"work_type: {attributes.work_type.value}")
    print(f"payment  : {attributes.payment}")
    print(f"address  : {attributes.address}")


if __name__ == "__main__":
    main()
