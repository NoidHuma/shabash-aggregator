import argparse
import csv
from pathlib import Path

from app.modules.coarse_filter.filter import MIN_TEXT_LENGTH


# Формирует из входного CSV новый, исключая публикации с текстом короче
# заданной длины (по умолчанию MIN_TEXT_LENGTH — тот же порог, что у грубого
# фильтра, чтобы датасет совпадал с тем, что реально видит ML в проде).


def main() -> None:
    parser = argparse.ArgumentParser(description="Drop rows whose text is shorter than N chars.")
    parser.add_argument("--in", dest="inp", required=True, help="Входной CSV")
    parser.add_argument("--out", default=None, help="Выходной CSV (по умолчанию <имя>_min<N>.csv)")
    parser.add_argument("--min-length", type=int, default=MIN_TEXT_LENGTH)
    args = parser.parse_args()

    inp = Path(args.inp)
    out = (
        Path(args.out)
        if args.out
        else inp.with_name(f"{inp.stem}_min{args.min_length}{inp.suffix}")
    )

    with inp.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    kept = [row for row in rows if len(row.get("text") or "") >= args.min_length]

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(kept)

    print(f"{inp} -> {out}")
    print(
        f"всего: {len(rows)}, оставлено (>= {args.min_length} симв.): {len(kept)}, "
        f"удалено: {len(rows) - len(kept)}"
    )


if __name__ == "__main__":
    main()
