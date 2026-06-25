from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import joblib


@dataclass
class RelevanceClassifier:

    pipeline: Any
    threshold: float
    metadata: dict | None = None

    @classmethod
    def load(cls, path: str) -> "RelevanceClassifier":
        bundle = joblib.load(path)
        return cls(
            pipeline=bundle["pipeline"],
            threshold=float(bundle["threshold"]),
            metadata=bundle.get("metadata"),
        )

    def predict_proba(self, text: str) -> float:
        return float(self.pipeline.predict_proba([text])[0][1])

    def predict(self, text: str) -> bool:
        return self.predict_proba(text) >= self.threshold
