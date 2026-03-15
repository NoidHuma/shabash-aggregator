import hashlib
import re


def normalize_text(text: str) -> str:
    """
    Приводит текст к виду,
    пригодному для дедупликации.

    Пример:

    'Привет!!! Мир'

    ->

    'приветмир'
    """

    text = text.lower()

    text = re.sub(r"\W+", "", text, flags=re.UNICODE)

    text = re.sub(r"_+", "", text)

    return text


def calculate_text_hash(text: str) -> str:
    """
    Считает SHA256 от нормализованного текста.
    """

    normalized_text = normalize_text(text)

    return hashlib.sha256(
        normalized_text.encode("utf-8")
    ).hexdigest()