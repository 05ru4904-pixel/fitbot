from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    telegram_bot_token: str
    gemini_api_key: str
    database_url: str
    webapp_url: str = "https://example.com/app"

    @property
    def async_database_url(self) -> str:
        # Railway gives postgresql://, SQLAlchemy async needs postgresql+asyncpg://
        url = self.database_url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url


settings = Settings()
