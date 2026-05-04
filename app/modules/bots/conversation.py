from dataclasses import dataclass

from app.core.config import settings
from app.modules.bots import keyboards as kb
from app.modules.bots import texts
from app.modules.bots import wizard


@dataclass
class Out:
    text: str
    keyboard: kb.Keyboard | None = None
    edit: bool = False  # True -> отредактировать текущее сообщение; False -> новое


START_TRIGGERS = {"/start", "старт"}


def handle_command(user, text: str, is_new: bool) -> list[Out]:
    """Обработка обычного сообщения (/start, текст) — возвращает НОВЫЕ сообщения."""
    text = (text or "").strip()
    lowered = text.lower()

    if is_new:
        user.status = "active"
        _reset_wizard(user)
        return [Out(texts.WELCOME), Out(texts.MENU, kb.MENU_KB)]

    if lowered in START_TRIGGERS:
        if user.status == "paused":
            user.status = "active"
            return [Out(texts.WELCOME_BACK, kb.MENU_KB)]
        return [Out(texts.MENU, kb.MENU_KB)]

    if user.status == "paused":
        return [Out(texts.PAUSED_HINT, kb.START_BTN_KB)]
    return [Out(texts.MENU, kb.MENU_KB)]


def handle_callback(user, data: str) -> Out:
    """Нажатие inline-кнопки -> редактирование текущего сообщения (edit=True)."""
    data = (data or "").strip()

    # --- Главное меню ---
    if data == "support":
        return Out(
            texts.SUPPORT.format(tg=settings.bot_support_tg, vk=settings.bot_support_vk),
            kb.MENU_BTN_KB,
            edit=True,
        )
    if data == "pause":
        user.status = "paused"
        _reset_wizard(user)
        return Out(texts.PAUSED, kb.START_BTN_KB, edit=True)
    if data == "start":
        user.status = "active"
        return Out(texts.WELCOME_BACK, kb.MENU_KB, edit=True)
    if data == "menu":
        _reset_wizard(user)
        return Out(texts.MENU, kb.MENU_KB, edit=True)

    # --- Меню настроек фильтров (после ⚙) ---
    if data == "settings":
        _reset_wizard(user)
        return _settings_menu(user)

    if data == "reconf_all":
        user.wizard_mode = "all"
        user.wizard_step = 0
        user.wizard_draft = {}
        return _question(0)

    if data == "reconf_one":
        user.wizard_mode = "pick"
        user.wizard_draft = _current_draft(user)
        user.wizard_step = wizard.CONFIRM_STEP
        return _category_menu()

    # --- Отмена в любом месте мастера ---
    if data == "cancel":
        _reset_wizard(user)
        return Out(texts.NOT_SAVED, kb.MENU_BTN_KB, edit=True)

    # --- Выбор категории -> подменю фильтров ---
    if data.startswith("cat") and data[3:].isdigit():
        return _filter_submenu(user, int(data[3:]))

    # --- Выбор конкретного фильтра ---
    if data.startswith("f") and data[1:].isdigit():
        idx = int(data[1:])
        user.wizard_mode = "pick"
        user.wizard_step = idx
        if user.wizard_draft is None:
            user.wizard_draft = _current_draft(user)
        return _question(idx)

    # --- Ответ на вопрос фильтра ---
    if data.startswith("opt") and data[3:].isdigit():
        return _answer(user, int(data[3:]))

    # --- Подтверждение ---
    if data == "save":
        _apply_draft(user)
        _reset_wizard(user)
        return Out(texts.SAVED, kb.MENU_BTN_KB, edit=True)
    if data == "edit":
        return _category_menu()

    return Out(texts.MENU, kb.MENU_KB, edit=True)


# --- Экраны ---

def _settings_menu(user) -> Out:
    text = (
        "Вот твои текущие фильтры:\n\n"
        + wizard.summary_text(_current_draft(user))
        + "\n\nХочешь изменить их?\n\n"
        "1 - Перенастроить фильтры с нуля\n"
        "2 - Изменить какой-то конкретный фильтр\n"
        "3 - Вернуться назад"
    )
    return Out(text, kb.SETTINGS_KB, edit=True)


def _category_menu() -> Out:
    lines = [f"{i} - {name}" for i, (name, _) in enumerate(wizard.CATEGORIES, start=1)]
    text = "Какой фильтр хочешь изменить? Выбери категорию:\n\n" + "\n".join(lines)
    return Out(text, kb.CATEGORY_KB, edit=True)


def _filter_submenu(user, cat_num: int) -> Out:
    if cat_num < 1 or cat_num > len(wizard.CATEGORIES):
        return _category_menu()
    name, indices = wizard.CATEGORIES[cat_num - 1]
    draft = user.wizard_draft or _current_draft(user)
    text = (
        f"Категория «{name}». Текущие настройки:\n\n"
        + wizard.category_filters_text(indices, draft)
        + "\n\nВыбери номер фильтра, который хочешь изменить."
    )
    return Out(text, kb.filter_pick_kb(indices), edit=True)


def _question(step_index: int) -> Out:
    n = len(wizard.FILTERS[step_index].options)
    return Out(wizard.question_text(step_index), kb.options_kb(n), edit=True)


def _answer(user, option: int) -> Out:
    step_index = user.wizard_step
    if step_index is None or step_index >= wizard.CONFIRM_STEP:
        return _confirm(user)

    flt = wizard.FILTERS[step_index]
    if option < 1 or option > len(flt.assignments):
        return _question(step_index)

    draft = dict(user.wizard_draft or {})
    draft.update(flt.assignments[option - 1])
    user.wizard_draft = draft

    # Полная перенастройка — идём к следующему вопросу; иначе сразу к подтверждению.
    if user.wizard_mode == "all":
        nxt = step_index + 1
        if nxt < wizard.CONFIRM_STEP:
            user.wizard_step = nxt
            return _question(nxt)

    user.wizard_step = wizard.CONFIRM_STEP
    return _confirm(user)


def _confirm(user) -> Out:
    text = (
        texts.CONFIRM_PROMPT.format(summary=wizard.summary_text(user.wizard_draft or {}))
        + "\n\n1 - Да, сохранить новые фильтры\n"
        "2 - Нет, внести изменения\n"
        "3 - Нет, отменить настройку новых фильтров"
    )
    return Out(text, kb.CONFIRM_KB, edit=True)


# --- Черновик / состояние ---

def _current_draft(user) -> dict:
    return {field: bool(getattr(user, field)) for field in wizard.ALL_FIELDS}


def _apply_draft(user) -> None:
    for field, value in (user.wizard_draft or {}).items():
        if field in wizard.ALL_FIELDS:
            setattr(user, field, bool(value))


def _reset_wizard(user) -> None:
    user.wizard_step = None
    user.wizard_draft = None
    user.wizard_mode = None
