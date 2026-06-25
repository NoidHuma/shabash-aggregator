import csv
from dataclasses import dataclass


@dataclass
class Sample:
    post_id: str
    source_id: str
    source: str
    text: str
    label: int


def load_samples(
    path: str,
    min_length: int = 30,
) -> list[Sample]:

    samples: list[Sample] = []

    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            label = (row.get("label") or "").strip()
            if label not in ("0", "1"):
                continue

            text = row.get("text") or ""
            if len(text) < min_length:
                continue

            samples.append(
                Sample(
                    post_id=(row.get("post_id") or "").strip(),
                    source_id=(row.get("source_id") or "").strip(),
                    source=(row.get("source") or "").strip().upper(),
                    text=text,
                    label=int(label),
                )
            )

    return samples
