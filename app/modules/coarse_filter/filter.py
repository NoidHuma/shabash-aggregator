from app.domain.post import Post


MIN_TEXT_LENGTH = 30


def passes_coarse_filter(post: Post) -> bool:

    return len(post.text) >= MIN_TEXT_LENGTH
