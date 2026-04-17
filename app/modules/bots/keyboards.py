from dataclasses import dataclass


# Цвет кнопки. В Telegram игнорируется (только эмодзи на подписи),
# в VK маппится: green->positive, blue->primary, red->negative, default->secondary.
@dataclass
class Button:
    label: str
    color: str = "default"


# Клавиатура — список рядов кнопок.
Keyboard = list[list[Button]]


MENU_KB: Keyboard = [
    [Button("⚙", "green")],
    [Button("🎧", "blue")],
    [Button("🚫", "red")],
]

MENU_ONLY_KB: Keyboard = [[Button("Меню", "green")]]

START_KB: Keyboard = [[Button("Старт", "green")]]

# Для всех шагов мастера: 1 и 2 — зелёные, 3 (прервать) — красная.
WIZARD_KB: Keyboard = [[Button("1", "green"), Button("2", "green"), Button("3", "red")]]

CONFIRM_KB: Keyboard = [[Button("Да", "green"), Button("Нет", "red")]]
