from dataclasses import dataclass


@dataclass
class Button:
    label: str
    data: str
    color: str = "default"


Keyboard = list[list[Button]]


_MAX_PER_ROW = 5


def _rows(buttons: list[Button], per_row: int = _MAX_PER_ROW) -> Keyboard:
    return [buttons[i:i + per_row] for i in range(0, len(buttons), per_row)]


MENU_KB: Keyboard = [
    [Button("⚙", "settings", "green")],
    [Button("🎧", "support", "blue")],
    [Button("🚫", "pause", "red")],
]

MENU_BTN_KB: Keyboard = [[Button("Меню", "menu", "green")]]

START_BTN_KB: Keyboard = [[Button("Старт", "start", "green")]]

SETTINGS_KB: Keyboard = [
    [
        Button("1", "reconf_all", "green"),
        Button("2", "reconf_one", "green"),
        Button("3", "menu", "red"),
    ]
]

CATEGORY_KB: Keyboard = [
    [
        Button("1", "cat1", "green"),
        Button("2", "cat2", "green"),
        Button("3", "cat3", "green"),
        Button("4", "cat4", "green"),
    ],
    [Button("Отмена", "cancel", "red")],
]

CONFIRM_KB: Keyboard = [
    [
        Button("1", "save", "green"),
        Button("2", "edit", "red"),
        Button("3", "cancel", "red"),
    ]
]


def options_kb(n: int) -> Keyboard:
    buttons = [Button(str(i), f"opt{i}", "green") for i in range(1, n + 1)]
    return _rows(buttons) + [[Button("Отмена", "cancel", "red")]]


def filter_pick_kb(indices: list[int]) -> Keyboard:
    buttons = [Button(str(pos), f"f{idx}", "green") for pos, idx in enumerate(indices, start=1)]
    return _rows(buttons) + [[Button("Отмена", "cancel", "red")]]
