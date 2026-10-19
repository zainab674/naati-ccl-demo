"""Test setup: a real Postgres test database (TEST_DATABASE_URL), migrated with Alembic once per run and
truncated between tests. Point DATABASE_URL at it before the app is imported."""
import os

os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = "test-secret-key-that-is-long-enough-for-hs256"
os.environ.setdefault("TEST_DATABASE_URL", "postgresql+psycopg://ccl:ccl@localhost:5433/ccl_test")
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
os.environ["STORAGE_BACKEND"] = "local"
os.environ["PASSWORD_HASH_ITERATIONS"] = "1000"
os.environ["STT_PROVIDER"] = "mock"
os.environ["EVALUATOR_PROVIDER"] = "mock"
os.environ["EMAIL_PROVIDER"] = "console"
os.environ["ADMIN_EMAIL"] = "admin@example.com"
os.environ["ADMIN_PASSWORD"] = "admin-pass-123"
for key in ("STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", "GROQ_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY"):
    os.environ[key] = ""

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.settings import BASE_DIR, get_settings  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def migrated_db(tmp_path_factory):
    settings = get_settings()
    settings.local_storage_dir = tmp_path_factory.mktemp("storage")
    settings.scratch_dir = tmp_path_factory.mktemp("scratch")
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    cfg = Config(str(BASE_DIR / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def clean_db(migrated_db):
    from app.seed import seed
    from app.services import ratelimit
    from app.services.email import ConsoleProvider

    ratelimit.reset()
    ConsoleProvider.outbox.clear()

    # DELETE (child tables first) is far cheaper than TRUNCATE for a handful of rows per test.
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    with SessionLocal() as db:
        seed(db)
    yield


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


def signup(client, email="student@example.com", password="student-pass-1", **extra):
    body = {"first_name": "Sam", "last_name": "Student", "email": email, "password": password,
            "accept_terms": True, **extra}
    r = client.post("/api/auth/signup", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def login(client, email, password):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture
def student_client(client):
    signup(client)
    return client


@pytest.fixture
def admin_client(client):
    login(client, "admin@example.com", "admin-pass-123")
    return client
