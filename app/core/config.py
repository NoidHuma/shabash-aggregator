from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    # PostgreSQL
    postgres_host: str
    postgres_port: int
    postgres_db: str
    postgres_user: str
    postgres_password: str

    database_url: str

    # Redis
    redis_host: str
    redis_port: int

    # Telegram скрапинг
    tg_api_id: int
    tg_api_hash: str
    tg_session_name: str = "tg_scraper"
    tg_poll_interval: int = 60
    tg_messages_per_request: int = 50
    tg_flood_sleep_threshold: int = 60

    # VK скрапинг
    vk_token: str
    vk_poll_interval: int = 60
    vk_posts_per_request: int = 50
    vk_requests_per_second: float = 3.0
    vk_max_retries: int = 3
    vk_request_timeout: float = 10.0

    # Модель фильтрации
    ml_model_path: str = "models/relevance_clf.joblib"

    # LLM извлечение атрибутов
    llm_api_key: str = ""
    llm_base_url: str = "https://api.mistral.ai/v1"
    llm_model: str = "ministral-14b-2512"
    llm_timeout: float = 30.0
    llm_max_retries: int = 3
    llm_requests_per_second: float = 0.38
    llm_enabled: bool = False

    # Публикаторы
    # VK-сообщество
    vk_publish_group_id: int = 0
    vk_publish_token: str = ""
    vk_publish_user_token: str = ""
    # Telegram-канал
    tg_channel: str = ""
    tg_bot_token: str = ""
    # Пауза
    publish_min_interval: float = 1.0
    # TG-бот
    tg_bot_dispatch_token: str = ""

    # поддержка
    bot_support_tg: str = "t.me/shabashsupport"
    bot_support_vk: str = "vk.com/at1mon1n"

    class Config:
        env_file = ".env"


settings = Settings()
