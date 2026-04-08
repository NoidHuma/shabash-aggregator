import argparse
import csv
import random
import sys
from collections import Counter
from collections import defaultdict
from pathlib import Path

from app.ml.data import load_samples


FIELDNAMES = ["post_id", "source_id", "source", "text", "label"]


def write_samples(path: Path, samples: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for s in samples:
            writer.writerow(
                {
                    "post_id": s.post_id,
                    "source_id": s.source_id,
                    "source": s.source,
                    "text": s.text,
                    "label": s.label,
                }
            )


def describe(name: str, samples: list) -> None:
    by_label = Counter(s.label for s in samples)
    by_source = Counter(s.source for s in samples)
    print(
        f"{name}: {len(samples)}  | label 1:{by_label.get(1,0)} 0:{by_label.get(0,0)}  "
        f"| {dict(by_source)}"
    )


def stratified_split(
    samples: list,
    test_fraction: float,
    seed: int,
) -> tuple[list, list]:
    """
    Стратификация по (source_id, label).

    Для каждой пары (источник, класс) случайно отбирает int(n * test_fraction)
    публикаций в test (floor/усечение — как в примере пользователя:
    749 -> 112, 72 -> 10). Остальные идут в train.

    Если группа состоит ровно из 1 публикации — она уходит в train
    (test всё равно бы получился пустым).
    """

    rng = random.Random(seed)

    groups: dict[tuple[str, int], list] = defaultdict(list)
    for s in samples:
        groups[(s.source_id, s.label)].append(s)

    train: list = []
    test: list = []

    print("\nРазбиение по (source_id, label):")
    for key in sorted(groups.keys(), key=lambda k: (k[0], k[1])):
        items = groups[key]
        n = len(items)
        n_test = int(n * test_fraction)

        if n_test >= n:
            n_test = n - 1
        if n < 2:
            n_test = 0

        indices = list(range(n))
        rng.shuffle(indices)
        test_idx = set(indices[:n_test])

        for i, item in enumerate(items):
            (test if i in test_idx else train).append(item)

        source_id, label = key
        print(
            f"  {source_id}  label={label}  всего={n}  -> train={n - n_test}  test={n_test}"
        )

    return train, test


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Per-source stratified train/test split (по 15% от 1 и 0 в каждом источнике)."
    )
    parser.add_argument("--in", dest="inp", default="data/dataset/dataset_labeled_min30.csv")
    parser.add_argument("--train-out", default="data/dataset/train.csv")
    parser.add_argument("--test-out", default="data/dataset/test.csv")
    parser.add_argument("--test-fraction", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    samples = load_samples(args.inp)
    if not samples:
        raise SystemExit("Нет пригодных размеченных примеров (label 0/1, текст >= 30). Проверь файл.")

    describe("Всего пригодных", samples)

    train, test = stratified_split(samples, args.test_fraction, args.seed)

    write_samples(Path(args.train_out), train)
    write_samples(Path(args.test_out), test)

    print()
    describe("Train", train)
    describe("Test ", test)
    print(f"\nЗаписано:\n  {args.train_out}\n  {args.test_out}")


if __name__ == "__main__":
    main()
