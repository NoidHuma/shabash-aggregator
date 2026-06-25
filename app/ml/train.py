import argparse
import platform
import sys
from datetime import datetime

import numpy as np
import sklearn
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.metrics import f1_score
from sklearn.metrics import precision_recall_curve
from sklearn.model_selection import StratifiedKFold
from sklearn.model_selection import cross_val_predict
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import FeatureUnion
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

from app.ml.save_classifier import save_classifier
from app.ml.data import load_samples
from app.ml.preprocessing import clean_text


CANDIDATES = ["logreg", "svm", "nb"]


def build_features() -> FeatureUnion:
    return FeatureUnion(
        [
            (
                "word",
                TfidfVectorizer(
                    preprocessor=clean_text,
                    analyzer="word",
                    ngram_range=(1, 2),
                    sublinear_tf=True,
                    min_df=2,
                ),
            ),
            (
                "char",
                TfidfVectorizer(
                    preprocessor=clean_text,
                    analyzer="char_wb",
                    ngram_range=(3, 5),
                    sublinear_tf=True,
                    min_df=2,
                ),
            ),
        ]
    )


def build_classifier(name: str, c: float):
    if name == "logreg":
        return LogisticRegression(class_weight="balanced", max_iter=1000, C=c)
    if name == "svm":
        return CalibratedClassifierCV(LinearSVC(class_weight="balanced", C=c))
    if name == "nb":
        return MultinomialNB()
    raise ValueError(f"Unknown model: {name}")


def make_pipeline(name: str, c: float) -> Pipeline:
    return Pipeline([("features", build_features()), ("clf", build_classifier(name, c))])


def benchmark(texts, y, folds: int, c: float, jobs: int) -> None:
    print("\n=== Кросс-валидация (сравнение моделей) ===")
    skf = StratifiedKFold(n_splits=folds, shuffle=True, random_state=42)
    for name in CANDIDATES:
        pipe = make_pipeline(name, c)
        y_pred = cross_val_predict(pipe, texts, y, cv=skf, n_jobs=jobs)
        print(f"\n--- {name} ---")
        print(classification_report(y, y_pred, digits=3, zero_division=0))


def tune_threshold(texts, y, name, c, folds, jobs, target_precision):
    skf = StratifiedKFold(n_splits=folds, shuffle=True, random_state=42)
    pipe = make_pipeline(name, c)
    proba = cross_val_predict(pipe, texts, y, cv=skf, method="predict_proba", n_jobs=jobs)[:, 1]

    if target_precision is not None:
        prec, rec, thr = precision_recall_curve(y, proba)
        best_t, best_r = 0.5, -1.0
        for p, r, t in zip(prec[:-1], rec[:-1], thr):
            if p >= target_precision and r > best_r:
                best_t, best_r = float(t), float(r)
        print(
            f"\nПорог под precision>={target_precision}: {best_t:.3f} "
            f"(recall на CV ≈ {best_r:.3f})"
        )
        return best_t

    best_t, best_f1 = 0.5, -1.0
    for t in np.arange(0.05, 0.96, 0.01):
        f1 = f1_score(y, (proba >= t).astype(int), average="macro", zero_division=0)
        if f1 > best_f1:
            best_f1, best_t = f1, float(t)
    print(f"\nПорог по максимуму macro-F1: {best_t:.3f} (macro-F1 на CV ≈ {best_f1:.3f})")
    return best_t


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the relevance classifier.")
    parser.add_argument("--train", default="data/dataset/train.csv")
    parser.add_argument("--out", default="models/relevance_clf.joblib")
    parser.add_argument("--model", choices=CANDIDATES, default="logreg")
    parser.add_argument("--C", type=float, default=1.0, help="Сила регуляризации (logreg/svm)")
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--jobs", type=int, default=1, help="Параллелизм CV (-1 = все ядра)")
    parser.add_argument(
        "--target-precision",
        type=float,
        default=None,
        help="Если задано — порог под эту precision; иначе максимизируем F1",
    )
    parser.add_argument("--no-benchmark", action="store_true")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    samples = load_samples(args.train)
    if not samples:
        raise SystemExit("Пустой train. Сначала размечай и сделай split.")

    texts = [s.text for s in samples]
    y = np.array([s.label for s in samples])

    n_pos, n_neg = int((y == 1).sum()), int((y == 0).sum())
    print(f"Train: {len(samples)} (релевантных 1:{n_pos}, нерелевантных 0:{n_neg})")

    if not args.no_benchmark:
        benchmark(texts, y, args.folds, args.C, args.jobs)

    print(f"\n=== Финальная модель: {args.model} (C={args.C}) ===")
    threshold = tune_threshold(
        texts, y, args.model, args.C, args.folds, args.jobs, args.target_precision
    )

    pipeline = make_pipeline(args.model, args.C)
    pipeline.fit(texts, y)

    metadata = {
        "trained_at": datetime.now().isoformat(timespec="seconds"),
        "train_file": args.train,
        "n_train": len(samples),
        "class_counts": {"relevant": n_pos, "irrelevant": n_neg},
        "model": args.model,
        "C": args.C,
        "threshold": threshold,
        "min_text_length": 30,
        "sklearn_version": sklearn.__version__,
        "python_version": platform.python_version(),
    }

    save_classifier(args.out, pipeline, threshold, metadata)
    print(f"\nМодель сохранена: {args.out}")
    print(f"Порог: {threshold:.3f}")


if __name__ == "__main__":
    main()
