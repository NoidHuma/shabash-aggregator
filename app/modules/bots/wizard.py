from dataclasses import dataclass


@dataclass
class WizardStep:
    question: str
    options: list[str]
    field: str
    values: dict[str, bool]  # "1"/"2" -> bool


_YESNO_OPTIONS = ["1 - Да", "2 - Нет", "3 - Прервать настройку фильтров"]
_YESNO_VALUES = {"1": True, "2": False}


STEPS: list[WizardStep] = [
    WizardStep(
        "Хочешь ли ты получать сообщения о заявках, где не указана оплата?",
        [
            "1 - Только заявки с указанной оплатой",
            "2 - Заявки и с указанной оплатой, и без нее",
            "3 - Прервать настройку фильтров",
        ],
        "payment_required",
        {"1": True, "2": False},
    ),
    WizardStep(
        "Хочешь ли ты получать сообщения о заявках, где не указан адрес?",
        [
            "1 - Только заявки с указанным адресом",
            "2 - Заявки и с указанным адресом, и без него",
            "3 - Прервать настройку фильтров",
        ],
        "address_required",
        {"1": True, "2": False},
    ),
    WizardStep("Хочешь ли ты получать сообщения о заявках для разнорабочих?", _YESNO_OPTIONS, "wt_handyman", _YESNO_VALUES),
    WizardStep("Хочешь ли ты получать сообщения о заявках для грузчиков?", _YESNO_OPTIONS, "wt_loader", _YESNO_VALUES),
    WizardStep("Хочешь ли ты получать сообщения о заявках для узких специалистов?", _YESNO_OPTIONS, "wt_specialist", _YESNO_VALUES),
    WizardStep("Хочешь ли ты получать сообщения о заявках, у которых не удалось определить характер работы?", _YESNO_OPTIONS, "wt_unknown", _YESNO_VALUES),
    WizardStep("Хочешь ли ты получать сообщения о коротких разовых заявках (от нескольких минут до 6 часов)?", _YESNO_OPTIONS, "dur_short_task", _YESNO_VALUES),
    WizardStep("Хочешь ли ты получать сообщения о разовых заявках на целую смену (6-12 часов; возможно, на несколько дней)?", _YESNO_OPTIONS, "dur_full_shift", _YESNO_VALUES),
    WizardStep("Хочешь ли ты получать сообщения о заявках на постоянную работу?", _YESNO_OPTIONS, "dur_permanent", _YESNO_VALUES),
    WizardStep("Хочешь ли ты получать сообщения о заявках на вахту?", _YESNO_OPTIONS, "dur_vahta", _YESNO_VALUES),
    WizardStep("Хочешь ли ты получать сообщения о заявках, у которых не удалось определить длительность работы?", _YESNO_OPTIONS, "dur_unknown", _YESNO_VALUES),
]

CONFIRM_STEP = len(STEPS)


def question_text(step_index: int) -> str:
    step = STEPS[step_index]
    return step.question + "\n\n" + "\n".join(step.options)


# Человекочитаемые подписи для сводки.
_SUMMARY_LABELS = [
    ("payment_required", "Оплата", {True: "только с указанной оплатой", False: "с оплатой и без"}),
    ("address_required", "Адрес", {True: "только с указанным адресом", False: "с адресом и без"}),
    ("wt_handyman", "Заявки для разнорабочих", {True: "да", False: "нет"}),
    ("wt_loader", "Заявки для грузчиков", {True: "да", False: "нет"}),
    ("wt_specialist", "Заявки для узких специалистов", {True: "да", False: "нет"}),
    ("wt_unknown", "Заявки с неопределённым характером работы", {True: "да", False: "нет"}),
    ("dur_short_task", "Короткие разовые заявки", {True: "да", False: "нет"}),
    ("dur_full_shift", "Разовые на целую смену", {True: "да", False: "нет"}),
    ("dur_permanent", "Постоянная работа", {True: "да", False: "нет"}),
    ("dur_vahta", "Вахта", {True: "да", False: "нет"}),
    ("dur_unknown", "Заявки с неопределённой длительностью", {True: "да", False: "нет"}),
]


def summary_text(draft: dict) -> str:
    lines = []
    for field, label, mapping in _SUMMARY_LABELS:
        value = draft.get(field)
        if value is None:
            continue
        lines.append(f"{label}: {mapping[bool(value)]}")
    return "\n".join(lines)
