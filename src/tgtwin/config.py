from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    BOT_TOKEN: str = ""
    DATABASE_URL: str = ""
    SEND_ENABLED: bool = False
    TAKEOVER_HOURS: int = 3

    @property
    def takeover_hours(self) -> int:
        return self.TAKEOVER_HOURS
