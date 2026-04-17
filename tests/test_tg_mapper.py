from datetime import datetime
from datetime import timezone

from app.models.chats_tg import ChatTG
from app.modules.tg_scraper.mapper import build_message_url
from app.modules.tg_scraper.mapper import is_processable_message
from app.modules.tg_scraper.mapper import map_tg_message


class FakeEntity:
    def __init__(self, username=None):
        self.username = username


class FakeMessage:
    def __init__(
        self,
        id=1,
        raw_text="",
        chat=None,
        action=None,
        sticker=None,
        document=None,
        video=None,
        date=None,
        sender_id=None,
    ):
        self.id = id
        self.raw_text = raw_text
        self.chat = chat
        self.action = action
        self.sticker = sticker
        self.document = document
        self.video = video
        self.date = date or datetime(2026, 4, 23, 10, 0, tzinfo=timezone.utc)
        self.sender_id = sender_id


def _chat(chat_id, url):
    return ChatTG(chat_id=chat_id, title="t", url=url, is_active=True)


# --- build_message_url ---------------------------------------------------

def test_url_public_chat_uses_username():
    chat = _chat(-1001503637616, "https://t.me/gruzchiki_kdr")
    msg = FakeMessage(id=66694, chat=FakeEntity(username="gruzchiki_kdr"))
    assert build_message_url(chat, msg) == "https://t.me/gruzchiki_kdr/66694"


def test_url_private_chat_uses_stripped_id():
    chat = _chat(-1001950740300, "https://t.me/+o_-VI2630qQ2OTNi")
    msg = FakeMessage(id=124494, chat=FakeEntity(username=None))
    assert build_message_url(chat, msg) == "https://t.me/c/1950740300/124494"


def test_url_private_chat_when_chat_entity_missing():
    chat = _chat(-1001950740300, "https://t.me/+invite")
    msg = FakeMessage(id=10, chat=None)
    assert build_message_url(chat, msg) == "https://t.me/c/1950740300/10"


# --- is_processable_message ----------------------------------------------

def test_accepts_plain_text():
    assert is_processable_message(FakeMessage(raw_text="нужен грузчик")) is True


def test_accepts_photo_with_caption():
    # фото: document is None, есть подпись
    assert is_processable_message(FakeMessage(raw_text="вынести мусор")) is True


def test_accepts_video_with_caption():
    msg = FakeMessage(raw_text="смотри", document=object(), video=object())
    assert is_processable_message(msg) is True


def test_rejects_empty_text():
    assert is_processable_message(FakeMessage(raw_text="")) is False
    assert is_processable_message(FakeMessage(raw_text="   ")) is False


def test_rejects_service_message():
    assert is_processable_message(FakeMessage(raw_text="x", action=object())) is False


def test_rejects_sticker():
    assert is_processable_message(FakeMessage(raw_text="x", sticker=object())) is False


def test_rejects_non_video_document():
    msg = FakeMessage(raw_text="файл", document=object(), video=None)
    assert is_processable_message(msg) is False


# --- map_tg_message ------------------------------------------------------

def test_map_builds_post_and_details_fields():
    chat = _chat(-1001503637616, "https://t.me/gruzchiki_kdr")
    msg = FakeMessage(
        id=66694,
        raw_text="500/2 занести штукатурку",
        chat=FakeEntity(username="gruzchiki_kdr"),
        sender_id=777,
    )
    mapping = map_tg_message(message=msg, chat=chat, text_hash="h")
    assert mapping.post.source.value == "tg"
    assert mapping.post.text == "500/2 занести штукатурку"
    assert mapping.post.source_post_url == "https://t.me/gruzchiki_kdr/66694"
    assert mapping.post.source_chat_url == "https://t.me/gruzchiki_kdr"
    assert mapping.post.post_datetime.tzinfo is None
    assert mapping.chat_id == -1001503637616
    assert mapping.message_id == 66694
    assert mapping.sender_id == 777


if __name__ == "__main__":
    import sys

    mod = sys.modules[__name__]
    tests = [v for k, v in vars(mod).items() if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print(f"ALL OK ({len(tests)} tests)")
