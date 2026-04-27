from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    app_name: str = "Farmly Backend"
    debug: bool = True

    database_url: str = Field(..., min_length=1)

    jwt_secret_key: str = Field(..., min_length=16)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7
    otp_expire_minutes: int = 5
    otp_max_attempts: int = 5

    sms_ethiopia_api_key: str | None = None
    sms_ethiopia_base_url: str = "https://smsethiopia.et/api"

    debug_reset_token: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
