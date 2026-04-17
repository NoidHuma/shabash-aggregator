from app.enums.duration_type import DurationType
from app.enums.work_type import WorkType
from app.modules.attribute_extractor.extractor import LLMExtractor
from app.modules.attribute_extractor.extractor import StubExtractor
from app.modules.attribute_extractor.extractor import _clean_optional
from app.modules.attribute_extractor.extractor import _parse_enum
from app.modules.attribute_extractor.extractor import _to_attributes


class FakeClient:
    def __init__(self, payload):
        self._payload = payload

    def extract_json(self, text):
        return self._payload


def test_valid_payload():
    attrs = LLMExtractor(
        FakeClient(
            {
                "duration": "short_task",
                "work_type": "loader",
                "payment": "500/2",
                "address": "бургасская 43",
            }
        )
    ).extract("любой текст")
    assert attrs.duration == DurationType.SHORT_TASK
    assert attrs.work_type == WorkType.LOADER
    assert attrs.payment == "500/2"
    assert attrs.address == "бургасская 43"


def test_vahta_is_duration():
    attrs = _to_attributes({"duration": "vahta", "work_type": "specialist", "payment": None, "address": "Анапа"})
    assert attrs.duration == DurationType.VAHTA
    assert attrs.work_type == WorkType.SPECIALIST


def test_invalid_enum_falls_back_to_unknown():
    attrs = _to_attributes({"duration": "часто", "work_type": "грузчик-водитель", "payment": "x", "address": "y"})
    assert attrs.duration == DurationType.UNKNOWN
    assert attrs.work_type == WorkType.UNKNOWN


def test_enum_by_name_also_works():
    assert _parse_enum(WorkType, "LOADER") == WorkType.LOADER
    assert _parse_enum(DurationType, "FULL_SHIFT") == DurationType.FULL_SHIFT


def test_clean_optional():
    assert _clean_optional(None) is None
    assert _clean_optional("") is None
    assert _clean_optional("   ") is None
    assert _clean_optional("null") is None
    assert _clean_optional("Не удалось определить") is None
    assert _clean_optional("3000/8") == "3000/8"


def test_missing_fields_default_unknown_none():
    attrs = _to_attributes({})
    assert attrs.duration == DurationType.UNKNOWN
    assert attrs.work_type == WorkType.UNKNOWN
    assert attrs.payment is None
    assert attrs.address is None


def test_stub_extractor():
    attrs = StubExtractor().extract("что угодно")
    assert attrs.duration == DurationType.UNKNOWN
    assert attrs.work_type == WorkType.UNKNOWN
    assert attrs.payment is None
    assert attrs.address is None


if __name__ == "__main__":
    import sys

    mod = sys.modules[__name__]
    tests = [v for k, v in vars(mod).items() if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print(f"ALL OK ({len(tests)} tests)")
