import argparse
import asyncio
import csv
import logging
from collections import Counter
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

from app.core.logging import setup_logging
from app.db.database import SessionLocal


logger = logging.getLogger(__name__)


# Выгрузка уникальных по тексту публикаций для разметки.
# Уникальность — по posts.text_hash (SHA256 нормализованного текста),
# при дубле берётся запись с минимальным id.
EXPORT_QUERY = """
SELECT DISTINCT ON (p.text_hash)
    p.id AS post_id,
    COALESCE(dv.owner_id, dt.chat_id) AS source_id,
    p.source AS source,
    p.text AS text
FROM posts p
LEFT JOIN posts_details_vk dv ON dv.post_id = p.id
LEFT JOIN posts_details_tg dt ON dt.post_id = p.id
ORDER BY p.text_hash, p.id
"""

FIELDNAMES = ["post_id", "source_id", "source", "text", "label"]


async def fetch_titles(session) -> dict[int, str]:
    titles: dict[int, str] = {}

    vk = await session.execute(text("SELECT group_id, title FROM groups_vk"))
    for group_id, title in vk.all():
        titles[int(group_id)] = title

    tg = await session.execute(text("SELECT chat_id, title FROM chats_tg"))
    for chat_id, title in tg.all():
        titles[int(chat_id)] = title

    return titles


async def main() -> None:
    parser = argparse.ArgumentParser(description="Export unique posts to a labeling CSV.")
    parser.add_argument(
        "--out",
        default=None,
        help="Output CSV path (default: data/dataset/dataset_raw_<timestamp>.csv)",
    )
    args = parser.parse_args()

    setup_logging()

    out_path = (
        Path(args.out)
        if args.out
        else Path("data/dataset") / f"dataset_raw_{datetime.now():%Y%m%d_%H%M}.csv"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)

    async with SessionLocal() as session:
        result = await session.execute(text(EXPORT_QUERY))
        rows = result.all()
        titles = await fetch_titles(session)

    by_source = Counter()
    by_source_id = Counter()

    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()

        for post_id, source_id, source, text_value in rows:
            writer.writerow(
                {
                    "post_id": post_id,
                    "source_id": source_id,
                    "source": source,
                    "text": text_value,
                    "label": "",
                }
            )
            by_source[source] += 1
            by_source_id[int(source_id)] += 1

    logger.info("Exported %d unique posts -> %s", len(rows), out_path)

    print(f"\nИтого уникальных текстов: {len(rows)}")
    for source, count in sorted(by_source.items()):
        print(f"  {source}: {count}")

    print("\nПо источникам (source_id — title — уникальных):")
    for source_id, count in by_source_id.most_common():
        title = titles.get(source_id, "?")
        print(f"  {source_id}  {count:>5}  {title}")


if __name__ == "__main__":
    asyncio.run(main())
