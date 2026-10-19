"""Environment settings (secrets, endpoints, model names) and YAML rule config (scoring, test flow).

Rule values that the client may change (penalties, thresholds, pass marks) live in config/*.yaml, never in code.
"""
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
REPO_DIR = BASE_DIR.parent
CONFIG_DIR = BASE_DIR / "config"


class Settings(BaseSettings):
    # Repo-root .env first, backend/.env may override (both optional).
    model_config = SettingsConfigDict(env_file=(REPO_DIR / ".env", BASE_DIR / ".env"), extra="ignore")

    environment: str = "development"  # development | test | production
    app_url: str = "http://localhost:3000"
    secret_key: str = "dev-secret-change-me"
    cookie_secure: bool = False
    session_hours: int = 12
    password_hash_iterations: int = 310_000
    cors_origins: str = ""  # extra origins allowed to POST (comma-separated); APP_URL is always allowed

    admin_email: str = ""
    admin_password: str = ""
    admin_first_name: str = "Admin"
    admin_last_name: str = "User"

    database_url: str = "postgresql+psycopg://ccl:ccl@localhost:5433/ccl"
    test_database_url: str = "postgresql+psycopg://ccl:ccl@localhost:5433/ccl_test"

    storage_backend: str = "s3"  # s3 | local
    local_storage_dir: Path = BASE_DIR / "data" / "storage"
    s3_endpoint_url: str = ""
    s3_region: str = "ap-southeast-2"
    s3_bucket: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    media_download_max_mb: int = 50
    scratch_dir: Path = BASE_DIR / "data" / "tmp"

    stt_provider: str = "auto"  # groq | mock | auto
    groq_api_key: str = ""
    stt_model: str = "whisper-large-v3-turbo"
    stt_fallback_model: str = "whisper-large-v3"

    evaluator_provider: str = "auto"  # gemini | anthropic | openai | mock | auto
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash-lite"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-5-5"
    openai_api_key: str = ""
    openai_model: str = "gpt-5-mini"

    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_self_study: str = ""
    stripe_price_coaching: str = ""
    stripe_checkout_mode: str = "subscription"  # subscription | payment

    email_provider: str = "console"  # console | smtp | resend
    email_from: str = "Benchmark Education <no-reply@example.com>"
    email_reply_to: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_starttls: bool = True
    resend_api_key: str = ""

    # Content protection
    signed_url_ttl_seconds: int = 300
    media_requests_per_minute: int = 120
    key_fetches_per_grant: int = 3

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def resolved_stt(self) -> str:
        if self.stt_provider != "auto":
            return self.stt_provider
        return "groq" if self.groq_api_key else "mock"

    @property
    def resolved_evaluator(self) -> str:
        if self.evaluator_provider != "auto":
            return self.evaluator_provider
        if self.gemini_api_key:
            return "gemini"
        if self.anthropic_api_key:
            return "anthropic"
        if self.openai_api_key:
            return "openai"
        return "mock"


def _normalise_db_url(url: str) -> str:
    for prefix in ("postgres://", "postgresql://", "postgresql+psycopg2://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.database_url = _normalise_db_url(s.database_url)
    s.test_database_url = _normalise_db_url(s.test_database_url)
    if s.is_production:
        if s.secret_key == "dev-secret-change-me" or len(s.secret_key) < 32:
            raise RuntimeError("SECRET_KEY must be set to a long random value in production")
        s.cookie_secure = True  # session cookies only over HTTPS
    return s


def _load_yaml(name: str) -> dict:
    return yaml.safe_load((CONFIG_DIR / name).read_text(encoding="utf-8"))


@lru_cache
def ccl_config() -> dict:
    """Test flow rules: segment timing, recording window, repeats, mock test shape."""
    return _load_yaml("ccl.yaml")


@lru_cache
def scoring_config() -> dict:
    """Scoring rules from docs/SCORING_BRIEF.md: penalties, thresholds, pass marks."""
    return _load_yaml("scoring.yaml")
