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

    # Telegram (client API через Telethon)
    tg_api_id: int
    tg_api_hash: str
    tg_session_name: str = "tg_scraper"
    tg_poll_interval: int = 60
    tg_messages_per_request: int = 50
    # Порог, до которого Telethon сам пережидает FloodWait (секунды).
    tg_flood_sleep_threshold: int = 60

    # ML (фильтр релевантности)
    ml_model_path: str = "models/relevance_clf.joblib"

    # LLM (извлечение атрибутов). OpenAI-совместимый API (по умолчанию OpenRouter).
    llm_api_key: str = ""
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "qwen/qwen3-next-80b-a3b-instruct:free"
    llm_timeout: float = 30.0
    llm_max_retries: int = 3
    # Если False — используется заглушка (UNKNOWN/None), без обращений к LLM.
    llm_enabled: bool = False

    # VK
    vk_token: str
    vk_poll_interval: int = 60
    vk_posts_per_request: int = 50
    # Глобальный троттлинг запросов к VK API (лимит ~3 req/s на приложение).
    vk_requests_per_second: float = 3.0
    # Сколько раз повторить запрос при ошибке лимита (error_code 6) или
    # сетевом сбое (таймаут/обрыв соединения).
    vk_max_retries: int = 3
    # Таймаут одного HTTP-запроса к VK API, секунды.
    vk_request_timeout: float = 10.0

    class Config:
        env_file = ".env"


settings = Settings()
