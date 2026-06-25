import logging
from typing import Protocol

from app.domain.post_attributes import PostAttributes
from app.enums.duration_type import DurationType
from app.enums.work_type import WorkType
from app.modules.attribute_extractor.llm_client import LLMClient


logger = logging.getLogger(__name__)


# Значения, которые трактуем как «не определено» для строковых полей.
_NULL_STRINGS = {
    "null",
    "none",
    "-",
    "не указано",
    "не указан",
    "не удалось определить",
    "не удалось однозначно определить",
}


class AttributeExtractor(Protocol):
    def extract(self, text: str) -> PostAttributes: ...


class StubExtractor:
    """Заглушка: ничего не извлекает (всё UNKNOWN/None). Без обращений к LLM."""

    def extract(self, text: str) -> PostAttributes:
        return PostAttributes(
            duration=DurationType.UNKNOWN,
            work_type=WorkType.UNKNOWN,
            payment=None,
            address=None,
        )


class LLMExtractor:
    def __init__(self, client: LLMClient) -> None:
        self._client = client

    def extract(self, text: str) -> PostAttributes:
        payload = self._client.extract_json(text)
        return _to_attributes(payload)


def _to_attributes(payload: dict) -> PostAttributes:
    return PostAttributes(
        duration=_parse_enum(DurationType, payload.get("duration")),
        work_type=_parse_enum(WorkType, payload.get("work_type")),
        payment=_clean_optional(payload.get("payment")),
        address=_clean_optional(payload.get("address")),
    )


def _parse_enum(enum_cls, value):
    """Маппит значение LLM в enum по value или имени; иначе UNKNOWN."""
    unknown = enum_cls.UNKNOWN

    if value is None:
        return unknown

    raw = str(value).strip()

    for member in enum_cls:
        if member.value == raw.lower():
            return member

    try:
        return enum_cls[raw.upper()]
    except KeyError:
        logger.warning("Неизвестное значение %s для %s -> UNKNOWN", value, enum_cls.__name__)
        return unknown


def _clean_optional(value) -> str | None:
    if value is None:
        return None

    text = str(value).strip()
    if not text or text.lower() in _NULL_STRINGS:
        return None

    return text


def build_extractor() -> AttributeExtractor:
    from app.core.config import settings

    if settings.llm_enabled:
        logger.info("Attribute extractor: LLM (%s)", settings.llm_model)
        return LLMExtractor(LLMClient())

    logger.info("Attribute extractor: STUB (LLM_ENABLED=false)")
    return StubExtractor()
