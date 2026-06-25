import re


_ZERO_WIDTH = dict.fromkeys(
    map(ord, "​‌‍‎‏﻿"),
    None,
)

_WHITESPACE = re.compile(r"\s+")


def clean_text(text: str) -> str:

    if not text:
        return ""

    text = text.replace("\xa0", " ")
    text = text.translate(_ZERO_WIDTH)
    text = text.lower()
    text = _WHITESPACE.sub(" ", text)

    return text.strip()
