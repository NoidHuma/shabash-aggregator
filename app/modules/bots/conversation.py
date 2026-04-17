from dataclasses import dataclass

from app.core.config import settings
from app.modules.bots import keyboards as kb
from app.modules.bots import texts
from app.modules.bots import wizard


@dataclass
class OutMessage:
    text: str
    keyboard: kb.Keyboard | None = None


START_TRIGGERS = {"/start", "старт"}


def process(user, text: str, is_new: bool) -> list[OutMessage]:
    """
    Обрабатывает входящее сообщение пользователя бота.

    Мутирует поля user (status, wizard_step, wizard_draft, фильтры) — вызывающий
    транспорт сохраняет изменения и отправляет полученные OutMessage.
    Транспортно-независимая логика (общая для TG и VK).
    """

    text = (text or "").strip()
    lowered = text.lower()

    # Внутри мастера настройки — всё уходит в его обработчик.
    if user.wizard_step is not None:
        return _wizard_input(user, text)

    if is_new:
        user.status = "active"
        return [OutMessage(texts.WELCOME), OutMessage(texts.MENU, kb.MENU_KB)]

    if lowered in START_TRIGGERS:
        if user.status == "paused":
            user.status = "active"
            return [OutMessage(texts.WELCOME_BACK, kb.MENU_ONLY_KB)]
        return [OutMessage(texts.MENU, kb.MENU_KB)]

    if text == "⚙":
        user.wizard_step = 0
        user.wizard_draft = {}
        return [OutMessage(wizard.question_text(0), kb.WIZARD_KB)]

    if text == "🎧":
        return [OutMessage(texts.SUPPORT.format(phone=settings.bot_support_phone), kb.MENU_ONLY_KB)]

    if text == "🚫":
        user.status = "paused"
        return [OutMessage(texts.PAUSED, kb.START_KB)]

    if text == "Меню":
        return [OutMessage(texts.MENU, kb.MENU_KB)]

    # Нераспознанный ввод.
    if user.status == "paused":
        return [OutMessage(texts.PAUSED_HINT, kb.START_KB)]
    return [OutMessage(texts.MENU, kb.MENU_KB)]


def _wizard_input(user, text: str) -> list[OutMessage]:
    step_index = user.wizard_step

    # Стадия подтверждения.
    if step_index >= wizard.CONFIRM_STEP:
        if text == "Да":
            _apply_draft(user)
            _reset_wizard(user)
            return [OutMessage(texts.SAVED, kb.MENU_ONLY_KB)]
        if text == "Нет":
            _reset_wizard(user)
            return [OutMessage(texts.NOT_SAVED, kb.MENU_ONLY_KB)]
        return [OutMessage(texts.CONFIRM_PROMPT.format(summary=wizard.summary_text(user.wizard_draft or {})), kb.CONFIRM_KB)]

    step = wizard.STEPS[step_index]

    if text == "3":
        _reset_wizard(user)
        return [OutMessage(texts.ABORTED, kb.MENU_ONLY_KB)]

    if text in step.values:
        draft = dict(user.wizard_draft or {})
        draft[step.field] = step.values[text]
        user.wizard_draft = draft

        next_index = step_index + 1
        if next_index < wizard.CONFIRM_STEP:
            user.wizard_step = next_index
            return [OutMessage(wizard.question_text(next_index), kb.WIZARD_KB)]

        user.wizard_step = wizard.CONFIRM_STEP
        return [OutMessage(texts.CONFIRM_PROMPT.format(summary=wizard.summary_text(draft)), kb.CONFIRM_KB)]

    # Невалидный ввод — повторяем текущий вопрос.
    return [OutMessage(wizard.question_text(step_index), kb.WIZARD_KB)]


def _apply_draft(user) -> None:
    for field, value in (user.wizard_draft or {}).items():
        setattr(user, field, bool(value))


def _reset_wizard(user) -> None:
    user.wizard_step = None
    user.wizard_draft = None
