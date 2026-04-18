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


MENU_KB: Keyboard = [
    [Button("⚙", "settings", "green")],
    [Button("🎧", "support", "blue")],
    [Button("🚫", "pause", "red")],
]

# Одиночная кнопка «Меню» (вернуться в главное меню).
MENU_BTN_KB: Keyboard = [[Button("Меню", "menu", "green")]]

# Кнопка «Старт» (возобновить после паузы).
START_BTN_KB: Keyboard = [[Button("Старт", "start", "green")]]

# Шаги мастера: 1 и 2 — зелёные, 3 (прервать) — красная.
WIZARD_KB: Keyboard = [
    [Button("1", "w1", "green"), Button("2", "w2", "green"), Button("3", "w3", "red")]
]

CONFIRM_KB: Keyboard = [[Button("Да", "yes", "green"), Button("Нет", "no", "red")]]
