from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    BOT_TOKEN: str = ""
    DATABASE_URL: str = ""
    SEND_ENABLED: bool = False
    TAKEOVER_HOURS: int = 3
    TELEGRAM_PROXY: str = ""
    DEEPSEEK_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.deepseek.com"
    LLM_MODEL: str = "deepseek-flash"
    LLM_TIMEOUT: float = 20.0
    LLM_THINKING: bool = False
    LLM_MAX_TOKENS: int = 800
    HISTORY_LIMIT: int = 30
    PERSONA_PATH: str = "config/persona.md"
    MAX_REPLIES_PER_HOUR: int = 10

    @property
    def takeover_hours(self) -> int:
        return self.TAKEOVER_HOURS
