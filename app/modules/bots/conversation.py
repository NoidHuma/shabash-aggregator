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
    """
    Обработка обычного сообщения пользователя (/start, текст).
    Возвращает сообщения, которые нужно ОТПРАВИТЬ (новые).
    """
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

    # Любой другой ввод текстом.
    if user.status == "paused":
        return [Out(texts.PAUSED_HINT, kb.START_BTN_KB)]
    return [Out(texts.MENU, kb.MENU_KB)]


def handle_callback(user, data: str) -> Out:
    """
    Обработка нажатия inline-кнопки. Возвращает ОДНО действие — отредактировать
    текущее сообщение (edit=True), чтобы чат не засорялся вопросами и ответами.
    """
    data = (data or "").strip()

    if data == "settings":
        user.wizard_step = 0
        user.wizard_draft = {}
        return Out(wizard.question_text(0), kb.WIZARD_KB, edit=True)

    if data == "support":
        return Out(texts.SUPPORT.format(tg=settings.bot_support_tg, vk=settings.bot_support_vk), kb.MENU_BTN_KB, edit=True)

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

    if data in ("w1", "w2", "w3", "yes", "no"):
        return _wizard_callback(user, data)

    return Out(texts.MENU, kb.MENU_KB, edit=True)


def _wizard_callback(user, data: str) -> Out:
    step_index = user.wizard_step
    if step_index is None:
        return Out(texts.MENU, kb.MENU_KB, edit=True)

    # Стадия подтверждения.
    if step_index >= wizard.CONFIRM_STEP:
        if data == "yes":
            _apply_draft(user)
            _reset_wizard(user)
            return Out(texts.SAVED, kb.MENU_BTN_KB, edit=True)
        if data == "no":
            _reset_wizard(user)
            return Out(texts.NOT_SAVED, kb.MENU_BTN_KB, edit=True)
        return Out(
            texts.CONFIRM_PROMPT.format(summary=wizard.summary_text(user.wizard_draft or {})),
            kb.CONFIRM_KB,
            edit=True,
        )

    # Обычный шаг — ждём w1/w2/w3.
    if data == "w3":
        _reset_wizard(user)
        return Out(texts.ABORTED, kb.MENU_BTN_KB, edit=True)

    if data in ("w1", "w2"):
        choice = "1" if data == "w1" else "2"
        step = wizard.STEPS[step_index]
        draft = dict(user.wizard_draft or {})
        draft[step.field] = step.values[choice]
        user.wizard_draft = draft

        next_index = step_index + 1
        if next_index < wizard.CONFIRM_STEP:
            user.wizard_step = next_index
            return Out(wizard.question_text(next_index), kb.WIZARD_KB, edit=True)

        user.wizard_step = wizard.CONFIRM_STEP
        return Out(texts.CONFIRM_PROMPT.format(summary=wizard.summary_text(draft)), kb.CONFIRM_KB, edit=True)

    # Невалидное нажатие на этом шаге — перерисовываем текущий вопрос.
    return Out(wizard.question_text(step_index), kb.WIZARD_KB, edit=True)


def _apply_draft(user) -> None:
    for field, value in (user.wizard_draft or {}).items():
        setattr(user, field, bool(value))


def _reset_wizard(user) -> None:
    user.wizard_step = None
    user.wizard_draft = None
