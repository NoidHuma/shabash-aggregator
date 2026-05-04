from dataclasses import dataclass
from typing import Callable


@dataclass
class FilterDef:
    # Поля модели, которые меняет этот фильтр (обычно одно; у источника — два).
    fields: list[str]
    question: str
    # Описания вариантов ответа (нумерованные строки для текста сообщения).
    options: list[str]
    # Назначения для черновика, параллельно options: option N -> assignments[N-1].
    assignments: list[dict]
    # Подпись и рендер текущего значения для сводки.
    label: str
    render: Callable[[dict], str]


def _bool_render(field: str, yes: str, no: str) -> Callable[[dict], str]:
    return lambda draft: yes if draft.get(field) else no


_YESNO = ["1 - Да", "2 - Нет"]


def _yesno(field: str, question: str, label: str) -> FilterDef:
    return FilterDef(
        [field],
        question,
        _YESNO,
        [{field: True}, {field: False}],
        label,
        _bool_render(field, "да", "нет"),
    )


def _src_render(draft: dict) -> str:
    vk, tg = draft.get("src_vk"), draft.get("src_tg")
    if vk and tg:
        return "VK и Telegram"
    if vk:
        return "только VK"
    if tg:
        return "только Telegram"
    return "—"


# Порядок фильтров = порядок шагов мастера. Источник идёт самым первым.
FILTERS: list[FilterDef] = [
    FilterDef(
        ["src_vk", "src_tg"],
        "Из каких источников ты хочешь получать заявки?",
        ["1 - Из VK и Telegram", "2 - Только из VK", "3 - Только из Telegram"],
        [
            {"src_vk": True, "src_tg": True},
            {"src_vk": True, "src_tg": False},
            {"src_vk": False, "src_tg": True},
        ],
        "Источники",
        _src_render,
    ),
    FilterDef(
        ["payment_required"],
        "Хочешь ли ты получать сообщения о заявках, где не указана оплата?",
        ["1 - Только заявки с указанной оплатой", "2 - Заявки и с оплатой, и без неё"],
        [{"payment_required": True}, {"payment_required": False}],
        "Оплата",
        _bool_render("payment_required", "только с указанной оплатой", "с оплатой и без"),
    ),
    FilterDef(
        ["address_required"],
        "Хочешь ли ты получать сообщения о заявках, где не указан адрес?",
        ["1 - Только заявки с указанным адресом", "2 - Заявки и с адресом, и без него"],
        [{"address_required": True}, {"address_required": False}],
        "Адрес",
        _bool_render("address_required", "только с указанным адресом", "с адресом и без"),
    ),
    _yesno("wt_handyman", "Хочешь ли ты получать сообщения о заявках для разнорабочих?", "Заявки для разнорабочих"),
    _yesno("wt_loader", "Хочешь ли ты получать сообщения о заявках для грузчиков?", "Заявки для грузчиков"),
    _yesno("wt_specialist", "Хочешь ли ты получать сообщения о заявках для узких специалистов?", "Заявки для узких специалистов"),
    _yesno("wt_unknown", "Хочешь ли ты получать сообщения о заявках, у которых не удалось определить характер работы?", "Заявки с неопределённым характером работы"),
    _yesno("dur_short_task", "Хочешь ли ты получать сообщения о коротких разовых заявках (от нескольких минут до 6 часов)?", "Короткие разовые заявки"),
    _yesno("dur_full_shift", "Хочешь ли ты получать сообщения о разовых заявках на целую смену (6–12 часов; возможно, на несколько дней)?", "Разовые на целую смену"),
    _yesno("dur_permanent", "Хочешь ли ты получать сообщения о заявках на постоянную работу?", "Постоянная работа"),
    _yesno("dur_vahta", "Хочешь ли ты получать сообщения о заявках на вахту?", "Вахта"),
    _yesno("dur_unknown", "Хочешь ли ты получать сообщения о заявках, у которых не удалось определить длительность работы?", "Заявки с неопределённой длительностью"),
]

CONFIRM_STEP = len(FILTERS)

# Все поля модели, которыми управляет мастер (для черновика/применения).
ALL_FIELDS = [field for flt in FILTERS for field in flt.fields]

# Категории для двухуровневого выбора «изменить конкретный фильтр».
# (название, индексы фильтров в FILTERS)
CATEGORIES: list[tuple[str, list[int]]] = [
    ("Источник заявок", [0]),
    ("Оплата и адрес", [1, 2]),
    ("Характер работы", [3, 4, 5, 6]),
    ("Длительность", [7, 8, 9, 10, 11]),
]


def question_text(step_index: int) -> str:
    flt = FILTERS[step_index]
    return flt.question + "\n\n" + "\n".join(flt.options)


def summary_text(draft: dict) -> str:
    """Нумерованная сводка всех 12 фильтров по значениям из черновика."""
    lines = []
    for i, flt in enumerate(FILTERS, start=1):
        lines.append(f"{i}) {flt.label}: {flt.render(draft)}")
    return "\n".join(lines)


def category_filters_text(indices: list[int], draft: dict) -> str:
    """Нумерованный список фильтров одной категории с текущими значениями."""
    lines = []
    for pos, idx in enumerate(indices, start=1):
        flt = FILTERS[idx]
        lines.append(f"{pos}) {flt.label}: {flt.render(draft)}")
    return "\n".join(lines)
