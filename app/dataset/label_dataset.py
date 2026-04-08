import argparse
import asyncio
import csv
import glob
import os
import sys
from collections import Counter
from pathlib import Path

from sqlalchemy import text

from app.db.database import SessionLocal


# Метки в колонке label рабочего файла:
#   1 — релевантно, 0 — нерелевантно, u — спорно (в обучение не идёт),
#   пусто — ещё не размечено / пропущено.
LABEL_RELEVANT = "1"
LABEL_IRRELEVANT = "0"
LABEL_UNCERTAIN = "u"

KEY_TO_LABEL = {
    "t": LABEL_RELEVANT,
    "f": LABEL_IRRELEVANT,
    "u": LABEL_UNCERTAIN,
}

FIELDNAMES = ["post_id", "source_id", "source", "text", "label"]

DEFAULT_LABELED = Path("data/dataset/dataset_labeled.csv")


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def latest_raw() -> Path:
    files = sorted(glob.glob("data/dataset/dataset_raw_*.csv"))
    if not files:
        raise SystemExit("Не найден data/dataset/dataset_raw_*.csv — сначала сделай выгрузку.")
    return Path(files[-1])


def load_items(labeled_path: Path) -> list[dict]:
    source_path = labeled_path if labeled_path.exists() else latest_raw()

    with source_path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    for row in rows:
        row.setdefault("label", "")
        if row["label"] is None:
            row["label"] = ""

    # Источник за источником: группируем по source, затем по source_id, затем по id.
    rows.sort(key=lambda r: (r["source"], int(r["source_id"]), int(r["post_id"])))
    return rows


def save_items(items: list[dict], labeled_path: Path) -> None:
    labeled_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = labeled_path.with_suffix(labeled_path.suffix + ".tmp")

    with tmp_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in items:
            writer.writerow({k: row.get(k, "") for k in FIELDNAMES})

    os.replace(tmp_path, labeled_path)


async def fetch_titles() -> dict[int, str]:
    titles: dict[int, str] = {}
    async with SessionLocal() as session:
        vk = await session.execute(text("SELECT group_id, title FROM groups_vk"))
        for group_id, title in vk.all():
            titles[int(group_id)] = title
        tg = await session.execute(text("SELECT chat_id, title FROM chats_tg"))
        for chat_id, title in tg.all():
            titles[int(chat_id)] = title
    return titles


def next_unlabeled(items: list[dict], start: int) -> int:
    for j in range(max(start, 0), len(items)):
        if not items[j]["label"]:
            return j
    return len(items)


def render(items: list[dict], i: int, titles: dict[int, str]) -> None:
    clear_screen()

    total = len(items)
    counts = Counter(r["label"] for r in items if r["label"])
    labeled_total = sum(counts.values())

    row = items[i]
    source_id = int(row["source_id"])
    title = titles.get(source_id, "?")

    src_total = sum(1 for r in items if int(r["source_id"]) == source_id)
    src_labeled = sum(1 for r in items if int(r["source_id"]) == source_id and r["label"])

    print(
        f"Размечено всего: {labeled_total} / {total}   "
        f"(t:{counts.get(LABEL_RELEVANT, 0)}  f:{counts.get(LABEL_IRRELEVANT, 0)}  u:{counts.get(LABEL_UNCERTAIN, 0)})"
    )
    print(f"Источник: {row['source']}  {source_id}  «{title}»")
    print(f"Этот источник: {src_labeled} / {src_total}")
    current = f"  [текущая метка: {row['label']}]" if row["label"] else ""
    print(f"Публикация id: {row['post_id']}   (длина текста: {len(row['text'])}){current}")
    print("─" * 70)
    print(row["text"])
    print("─" * 70)
    print("[t] релевантно   [f] нерелевантно   [s] пропустить   [u] спорно   [b] назад   [q] выход")


def main() -> None:
    parser = argparse.ArgumentParser(description="Interactive dataset labeler.")
    parser.add_argument("--file", default=str(DEFAULT_LABELED), help="Рабочий файл с метками")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    labeled_path = Path(args.file)
    items = load_items(labeled_path)

    if not labeled_path.exists():
        save_items(items, labeled_path)

    titles = asyncio.run(fetch_titles())

    i = next_unlabeled(items, 0)

    while True:
        if i >= len(items):
            clear_screen()
            counts = Counter(r["label"] for r in items if r["label"])
            print(
                f"Все пройдено. Размечено {sum(counts.values())} / {len(items)} "
                f"(t:{counts.get(LABEL_RELEVANT,0)} f:{counts.get(LABEL_IRRELEVANT,0)} u:{counts.get(LABEL_UNCERTAIN,0)}).\n"
                "Остались пропущенные? Нажми [b] чтобы вернуться, или [q] для выхода."
            )
            choice = input("> ").strip().lower()
            if choice == "b":
                i = max(0, len(items) - 1)
            elif choice == "q":
                break
            continue

        render(items, i, titles)
        choice = input("> ").strip().lower()

        if choice in KEY_TO_LABEL:
            items[i]["label"] = KEY_TO_LABEL[choice]
            save_items(items, labeled_path)
            i = next_unlabeled(items, i + 1)
        elif choice == "s":
            i = next_unlabeled(items, i + 1)
        elif choice == "b":
            i = max(0, i - 1)
        elif choice == "q":
            break
        # любой другой ввод — просто перерисуем тот же экран

    clear_screen()
    counts = Counter(r["label"] for r in items if r["label"])
    print(
        f"Сохранено в {labeled_path}\n"
        f"Размечено {sum(counts.values())} / {len(items)} "
        f"(t:{counts.get(LABEL_RELEVANT,0)} f:{counts.get(LABEL_IRRELEVANT,0)} u:{counts.get(LABEL_UNCERTAIN,0)})"
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nПрервано. Размеченное сохранено.")
