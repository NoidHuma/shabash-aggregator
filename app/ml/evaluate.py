import argparse
import csv
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import average_precision_score
from sklearn.metrics import classification_report
from sklearn.metrics import confusion_matrix
from sklearn.metrics import roc_auc_score

from app.core.config import settings
from app.ml.classifier import RelevanceClassifier
from app.ml.data import load_samples


def report_block(title: str, y_true, y_pred, proba) -> str:
    lines = [f"\n===== {title} (n={len(y_true)}) ====="]
    if len(set(y_true)) < 2:
        lines.append("(в подвыборке один класс — часть метрик неинформативна)")
    lines.append(classification_report(y_true, y_pred, digits=3, zero_division=0))
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    lines.append("Матрица ошибок [строки=факт 0/1, столбцы=предсказание 0/1]:")
    lines.append(str(cm))
    try:
        lines.append(f"ROC-AUC: {roc_auc_score(y_true, proba):.3f}")
        lines.append(f"PR-AUC : {average_precision_score(y_true, proba):.3f}")
    except ValueError:
        pass
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the relevance classifier on the test set.")
    parser.add_argument("--test", default="data/dataset/test.csv")
    parser.add_argument("--model-path", default=settings.ml_model_path)
    parser.add_argument("--report", default="data/dataset/eval_report.txt")
    parser.add_argument("--dump-predictions", default="data/dataset/eval_predictions.csv")
    parser.add_argument("--dump-errors", default="data/dataset/eval_errors.csv")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    clf = RelevanceClassifier.load(args.model_path)
    samples = load_samples(args.test)
    if not samples:
        raise SystemExit("Пустой test.")

    proba = np.array([clf.predict_proba(s.text) for s in samples])
    y_true = np.array([s.label for s in samples])
    y_pred = (proba >= clf.threshold).astype(int)
    sources = np.array([s.source for s in samples])

    out = [
        f"Модель: {args.model_path}",
        f"Порог: {clf.threshold:.3f}",
        f"Метаданные: {clf.metadata}",
        report_block("ВСЕ источники", y_true, y_pred, proba),
    ]
    for src in ("VK", "TG"):
        mask = sources == src
        if mask.any():
            out.append(report_block(src, y_true[mask], y_pred[mask], proba[mask]))

    text = "\n".join(out)
    print(text)

    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(text, encoding="utf-8")
    print(f"\nОтчёт сохранён: {args.report}")

    # Полная выгрузка предсказаний по каждой тестовой публикации с пометкой
    # correct (1 — верно, 0 — ошибка). Колонку correct удобно фильтровать,
    # чтобы посмотреть отдельно верно/неверно классифицированные.
    header = ["post_id", "source_id", "source", "true", "pred", "correct", "proba", "text"]
    rows_out = []
    for s, p, pr in zip(samples, y_pred, proba):
        correct = int(int(p) == s.label)
        rows_out.append([s.post_id, s.source_id, s.source, s.label, int(p), correct, f"{pr:.3f}", s.text])

    with open(args.dump_predictions, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows_out)
    n_wrong = sum(1 for r in rows_out if r[5] == 0)
    print(f"\nВсе предсказания ({len(rows_out)}, ошибок {n_wrong}) -> {args.dump_predictions}")

    # Отдельный файл только с ошибками — для быстрого разбора спорных меток.
    errors = [r for r in rows_out if r[5] == 0]
    if errors:
        with open(args.dump_errors, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(errors)
        print(f"Только ошибки -> {args.dump_errors}")


if __name__ == "__main__":
    main()
