"""Start-up for serverless hosts (AUTO_MIGRATE=true, e.g. Vercel): bring the database schema up to date and seed the
reference data (languages, plans, the admin from ADMIN_EMAIL / ADMIN_PASSWORD). Runs once per cold start; a Postgres
advisory lock keeps concurrent instances from migrating at the same time. Docker deployments run these as commands."""
import logging

from sqlalchemy import text

from .db import SessionLocal, engine
from .settings import BASE_DIR

log = logging.getLogger("bootstrap")
_LOCK = 72_340_115  # any constant: identifies this lock among Postgres advisory locks


def migrate_and_seed() -> None:
    from alembic import command
    from alembic.config import Config

    from .seed import seed

    with engine.connect() as conn:
        conn.execute(text("select pg_advisory_lock(:k)"), {"k": _LOCK})
        try:
            cfg = Config(str(BASE_DIR / "alembic.ini"))
            cfg.set_main_option("script_location", str(BASE_DIR / "alembic"))
            command.upgrade(cfg, "head")
            with SessionLocal() as db:
                seed(db)
            log.info("database migrated and seeded")
        finally:
            conn.execute(text("select pg_advisory_unlock(:k)"), {"k": _LOCK})
            conn.commit()
