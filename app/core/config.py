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
    # Глобальный троттлинг запросов к LLM (лимит провайдера по запросам/сек).
    # Напр. 0.38 = не чаще 1 запроса раз в ~2.63 секунды.
    llm_requests_per_second: float = 0.38
    # Если False — используется заглушка (UNKNOWN/None), без обращений к LLM.
    llm_enabled: bool = False

    # Публикаторы (агрегирующие каналы)
    # VK-сообщество, куда постим (положительный id) + токен с правом wall+photos.
    vk_publish_group_id: int = 0
    vk_publish_token: str = ""
    # Telegram-канал (id вида -100... или @username) + токен бота-админа.
    tg_channel: str = ""
    tg_bot_token: str = ""
    # Пауза между публикациями (троттлинг под лимиты VK/Telegram), секунды.
    publish_min_interval: float = 1.0

    # Персональные боты (рассылка по пользовательским фильтрам)
    # TG-бот для личных сообщений (отдельный от канального).
    tg_bot_dispatch_token: str = ""
    # Заглушка телефона поддержки (пока фейк).
    bot_support_phone: str = "+7 (900) 123-45-67"

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
