from types import SimpleNamespace

from app.domain.post import Post
from app.domain.post_attributes import PostAttributes
from app.enums.duration_type import DurationType
from app.enums.post_source import PostSource
from app.enums.work_type import WorkType
from app.modules.bots.conversation import process
from app.modules.bots.filters import matches
from app.modules.bots.wizard import CONFIRM_STEP


def make_user():
    return SimpleNamespace(
        status="active",
        wizard_step=None,
        wizard_draft=None,
        payment_required=False,
        address_required=False,
        wt_loader=True,
        wt_handyman=True,
        wt_specialist=True,
        wt_unknown=True,
        dur_short_task=True,
        dur_full_shift=True,
        dur_permanent=True,
        dur_vahta=True,
        dur_unknown=True,
    )


def make_post(duration, work_type, payment=None, address=None):
    return Post(
        id=1, source=PostSource.VK, text="t",
        source_post_url="u", source_chat_url="c", attachments=[],
        attributes=PostAttributes(duration, work_type, payment, address),
    )


def test_new_user_gets_welcome_and_menu():
    u = make_user()
    out = process(u, "/start", is_new=True)
    assert len(out) == 2
    assert "Добро пожаловать" in out[0].text
    assert "⚙" in out[1].text and out[1].keyboard is not None
    assert u.status == "active"


def test_pause_then_resume():
    u = make_user()
    out = process(u, "🚫", is_new=False)
    assert u.status == "paused"
    assert "Старт" in out[0].keyboard[0][0].label
    out = process(u, "Старт", is_new=False)
    assert u.status == "active"
    assert "помню тебя" in out[0].text


def test_support_shows_menu_button():
    u = make_user()
    out = process(u, "🎧", is_new=False)
    assert "Поддержка" in out[0].text
    assert out[0].keyboard[0][0].label == "Меню"


def test_wizard_full_pass_and_save():
    u = make_user()
    process(u, "⚙", is_new=False)
    assert u.wizard_step == 0

    # payment: "1" -> only with payment (True); address: "2" -> both (False)
    process(u, "1", is_new=False)
    process(u, "2", is_new=False)
    # остальные 9 шагов отвечаем "2" (Нет)
    for _ in range(9):
        process(u, "2", is_new=False)
    assert u.wizard_step == CONFIRM_STEP

    out = process(u, "Да", is_new=False)
    assert "сохранены" in out[0].text
    assert u.wizard_step is None
    assert u.payment_required is True
    assert u.address_required is False
    assert u.wt_handyman is False and u.dur_vahta is False


def test_wizard_abort_does_not_save():
    u = make_user()
    process(u, "⚙", is_new=False)
    out = process(u, "3", is_new=False)
    assert "прервана" in out[0].text
    assert u.wizard_step is None
    assert u.payment_required is False  # не изменилось


def test_filters_match():
    u = make_user()
    p = make_post(DurationType.SHORT_TASK, WorkType.LOADER, payment="500/2", address="x")
    assert matches(u, p) is True

    u.wt_loader = False
    assert matches(u, p) is False

    u.wt_loader = True
    u.payment_required = True
    assert matches(u, make_post(DurationType.SHORT_TASK, WorkType.LOADER, payment=None)) is False

    u.payment_required = False
    u.dur_vahta = False
    assert matches(u, make_post(DurationType.VAHTA, WorkType.SPECIALIST)) is False


if __name__ == "__main__":
    import sys
    mod = sys.modules[__name__]
    tests = [v for k, v in vars(mod).items() if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print(f"ALL OK ({len(tests)} tests)")
