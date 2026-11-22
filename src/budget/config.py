from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://budget:budget@localhost:5432/budget"
    # No default on purpose: the app must not start with a guessable or short (<256 bit) key.
    jwt_secret: str = Field(min_length=32)
    jwt_expire_minutes: int = 60


settings = Settings()
