"""Start-up for serverless hosts (AUTO_MIGRATE=true, e.g. Vercel): bring the database schema up to date and seed the
reference data (languages, plans, the admin from ADMIN_EMAIL / ADMIN_PASSWORD). Runs once per cold start; a Postgres
advisory lock keeps concurrent instances from migrating at the same time. Everything runs in one transaction on one
connection, so the lock also holds behind a transaction-mode connection pooler (Neon, PgBouncer). Docker deployments
run these as commands."""
import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from .db import engine
from .settings import BASE_DIR

log = logging.getLogger("bootstrap")
_LOCK = 72_340_115  # any constant: identifies this lock among Postgres advisory locks


def migrate_and_seed() -> None:
    from alembic import command
    from alembic.config import Config

    from .seed import seed

    with engine.begin() as conn:  # commits at the end, which also releases the lock
        conn.execute(text("select pg_advisory_xact_lock(:k)"), {"k": _LOCK})
        cfg = Config(str(BASE_DIR / "alembic.ini"))
        cfg.set_main_option("script_location", str(BASE_DIR / "alembic"))
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")
        with Session(bind=conn, join_transaction_mode="create_savepoint") as db:
            seed(db)
    log.info("database migrated and seeded")
