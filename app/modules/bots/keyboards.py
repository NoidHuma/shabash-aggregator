from dataclasses import dataclass


# Inline-кнопка: подпись + callback-данные (что прислать боту по нажатию).
# color используется только в VK (green->positive, blue->primary,
# red->negative, default->secondary); в Telegram цвет inline-кнопок не задаётся.
@dataclass
class Button:
    label: str
    data: str
    color: str = "default"


# Клавиатура — список рядов кнопок (inline).
Keyboard = list[list[Button]]


# VK inline-клавиатура ограничена (≈5 кнопок в ряду, до 6 рядов) — раскладываем
# числовые кнопки рядами по 5.
_MAX_PER_ROW = 5


def _rows(buttons: list[Button], per_row: int = _MAX_PER_ROW) -> Keyboard:
    return [buttons[i:i + per_row] for i in range(0, len(buttons), per_row)]


MENU_KB: Keyboard = [
    [Button("⚙", "settings", "green")],
    [Button("🎧", "support", "blue")],
    [Button("🚫", "pause", "red")],
]

# Одиночная кнопка «Меню» (вернуться в главное меню).
MENU_BTN_KB: Keyboard = [[Button("Меню", "menu", "green")]]

# Кнопка «Старт» (возобновить после паузы).
START_BTN_KB: Keyboard = [[Button("Старт", "start", "green")]]

# Меню настроек (после ⚙): 1 - перенастроить всё, 2 - изменить один, 3 - назад.
SETTINGS_KB: Keyboard = [
    [
        Button("1", "reconf_all", "green"),
        Button("2", "reconf_one", "green"),
        Button("3", "menu", "red"),
    ]
]

# Выбор категории фильтра (1..4) + «Отмена».
CATEGORY_KB: Keyboard = [
    [
        Button("1", "cat1", "green"),
        Button("2", "cat2", "green"),
        Button("3", "cat3", "green"),
        Button("4", "cat4", "green"),
    ],
    [Button("Отмена", "cancel", "red")],
]

# Подтверждение: 1 - сохранить (зел.), 2 - внести изменения (кр.), 3 - отменить (кр.).
CONFIRM_KB: Keyboard = [
    [
        Button("1", "save", "green"),
        Button("2", "edit", "red"),
        Button("3", "cancel", "red"),
    ]
]


def options_kb(n: int) -> Keyboard:
    """Кнопки вариантов ответа на вопрос (1..n зелёные) + красная «Отмена»."""
    buttons = [Button(str(i), f"opt{i}", "green") for i in range(1, n + 1)]
    return _rows(buttons) + [[Button("Отмена", "cancel", "red")]]


def filter_pick_kb(indices: list[int]) -> Keyboard:
    """Кнопки выбора конкретного фильтра внутри категории + «Отмена».

    Подпись — локальный номер (1..N), данные — глобальный индекс фильтра f{idx}.
    """
    buttons = [Button(str(pos), f"f{idx}", "green") for pos, idx in enumerate(indices, start=1)]
    return _rows(buttons) + [[Button("Отмена", "cancel", "red")]]
