from typing import Any

import joblib


def save_classifier(
    path: str,
    pipeline: Any,
    threshold: float,
    metadata: dict,
) -> None:
    import os

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    joblib.dump(
        {
            "pipeline": pipeline,
            "threshold": threshold,
            "metadata": metadata,
        },
        path,
    )
