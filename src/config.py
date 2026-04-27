from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bot_token: str
    database_url: str = "sqlite+aiosqlite:///./data/jobtracker.db"
    linkedin_job_search_url: str | None = None
    log_level: str = "INFO"

    @property
    def resolved_database_url(self) -> str:
        url = self.database_url
        if url.startswith("sqlite+aiosqlite:///./"):
            rel = url.removeprefix("sqlite+aiosqlite:///./")
            abs_path = (_PROJECT_ROOT / rel).resolve()
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            return f"sqlite+aiosqlite:///{abs_path.as_posix()}"
        return url


def get_settings() -> Settings:
    return Settings()
