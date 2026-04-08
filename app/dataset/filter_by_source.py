import argparse
import csv
from pathlib import Path


# Формирует из входного CSV новый, оставляя только публикации одной платформы
# (VK или TG). Колонка source хранит значения "VK" / "TG".


def main() -> None:
    parser = argparse.ArgumentParser(description="Keep only rows of one source (VK or TG).")
    parser.add_argument("--in", dest="inp", required=True, help="Входной CSV")
    parser.add_argument(
        "--source",
        required=True,
        choices=["vk", "tg", "VK", "TG"],
        help="Какой источник оставить",
    )
    parser.add_argument("--out", default=None, help="Выходной CSV (по умолчанию <имя>_<src>.csv)")
    args = parser.parse_args()

    source = args.source.upper()
    inp = Path(args.inp)
    out = (
        Path(args.out)
        if args.out
        else inp.with_name(f"{inp.stem}_{source.lower()}{inp.suffix}")
    )

    with inp.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    kept = [row for row in rows if (row.get("source") or "").upper() == source]

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(kept)

    print(f"{inp} -> {out}")
    print(f"всего: {len(rows)}, оставлено ({source}): {len(kept)}")


if __name__ == "__main__":
    main()
