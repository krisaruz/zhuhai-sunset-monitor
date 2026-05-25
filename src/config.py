from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    sunsetbot_base_url: str = "https://sunsetbot.top/"
    sunsetbot_model: str = "EC"
    default_city: str = "珠海"

    feishu_webhook_url: str = ""
    feishu_webhook_secret: str | None = None

    notify_min_quality: float = 0.2

    database_url: str = "sqlite+aiosqlite:///./data/sunset.db"

    latitude: float = 22.27
    longitude: float = 113.58

    amap_key: str = ""

    model_config = {"env_file": ".env", "env_prefix": "SUNSET_"}


settings = Settings()
