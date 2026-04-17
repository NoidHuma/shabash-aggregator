from app.domain.post import Post
from app.enums.post_source import PostSource
from app.modules.coarse_filter.filter import MIN_TEXT_LENGTH
from app.modules.coarse_filter.filter import passes_coarse_filter


def _make_post(text: str) -> Post:
    return Post(
        id=1,
        source=PostSource.VK,
        text=text,
        source_post_url="https://vk.com/wall-1_1",
        source_chat_url="https://vk.com/test",
        attachments=[],
        attributes=None,
    )


def test_rejects_text_shorter_than_min():
    assert passes_coarse_filter(_make_post("a" * (MIN_TEXT_LENGTH - 1))) is False


def test_accepts_text_at_min_length():
    assert passes_coarse_filter(_make_post("a" * MIN_TEXT_LENGTH)) is True


def test_accepts_text_longer_than_min():
    assert passes_coarse_filter(_make_post("a" * (MIN_TEXT_LENGTH + 50))) is True


def test_rejects_empty_text():
    assert passes_coarse_filter(_make_post("")) is False


if __name__ == "__main__":
    test_rejects_text_shorter_than_min()
    test_accepts_text_at_min_length()
    test_accepts_text_longer_than_min()
    test_rejects_empty_text()
    print("ALL OK")
