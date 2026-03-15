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

    # VK
    vk_token: str

    class Config:
        env_file = ".env"


settings = Settings()
