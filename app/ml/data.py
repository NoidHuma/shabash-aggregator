import csv
from dataclasses import dataclass

from app.modules.coarse_filter.filter import MIN_TEXT_LENGTH


@dataclass
class Sample:
    post_id: str
    source_id: str
    source: str  # "VK" / "TG"
    text: str
    label: int  # 1 = релевантно, 0 = нерелевантно


def load_samples(
    path: str,
    min_length: int = MIN_TEXT_LENGTH,
) -> list[Sample]:
    """
    Загружает размеченные примеры из CSV.

    Берёт только строки с меткой 0/1 (пропускает 'u' и пустые) и только тексты
    длиной >= min_length — ровно то, что ML-фильтр видит в проде после грубого
    фильтра. Эти фильтры применяются ВЕЗДЕ (split/train/evaluate), чтобы выборки
    и метрики были согласованы с продакшеном.
    """

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
