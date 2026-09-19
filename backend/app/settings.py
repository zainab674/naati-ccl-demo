from functools import lru_cache
from pathlib import Path

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    database_url: str = f"sqlite:///{(BASE_DIR / 'data' / 'app.db').as_posix()}"
    secret_key: str = "dev-secret-change-me"
    data_dir: Path = BASE_DIR / "data"
    cookie_secure: bool = False

    # Providers. "auto" picks the real provider when a key is present, else the fallback.
    stt_provider: str = "auto"          # openai | groq | mock | auto
    marker_provider: str = "auto"       # claude | heuristic | auto
    anthropic_api_key: str | None = None
    anthropic_base_url: str = "https://api.anthropic.com"
    claude_model: str = "claude-opus-5"
    openai_api_key: str | None = None
    groq_api_key: str | None = None

    # Content protection
    signed_url_ttl_seconds: int = 300
    media_requests_per_minute: int = 60
    key_fetches_per_grant: int = 3

    @property
    def media_dir(self) -> Path:
        return self.data_dir / "media"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def resolved_stt(self) -> str:
        if self.stt_provider != "auto":
            return self.stt_provider
        if self.groq_api_key:
            return "groq"
        if self.openai_api_key:
            return "openai"
        return "mock"

    @property
    def resolved_marker(self) -> str:
        if self.marker_provider != "auto":
            return self.marker_provider
        return "claude" if self.anthropic_api_key else "heuristic"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.media_dir.mkdir(parents=True, exist_ok=True)
    s.uploads_dir.mkdir(parents=True, exist_ok=True)
    return s


@lru_cache
def ccl_config() -> dict:
    return yaml.safe_load((BASE_DIR / "config" / "ccl.yaml").read_text(encoding="utf-8"))


@lru_cache
def rubric_config() -> dict:
    return yaml.safe_load((BASE_DIR / "config" / "rubric.yaml").read_text(encoding="utf-8"))
