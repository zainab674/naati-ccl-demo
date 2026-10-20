"""Idempotent base data: languages, their English pairs and scoring guidance, topics, plans, first admin.

    python -m app.seed

Safe to run on every deploy: existing rows are kept; the admin account is kept in sync with ADMIN_EMAIL /
ADMIN_PASSWORD. No demo students, reviews or prices are created here.
"""
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import SessionLocal
from .models import Language, LanguageScoringConfig, LanguageType, Plan, SiteContent, Topic, User, UserRole
from .seed_languages import LANGUAGES, SCORING
from .security import hash_password, verify_password
from .services.languages import get_or_create_pair
from .settings import get_settings

log = logging.getLogger("seed")

# Common CCL dialogue domains.
TOPICS = ["Health", "Legal", "Financial", "Education", "Community", "Consumer Affairs", "Immigration",
          "Employment", "Housing", "Social Services", "Business", "Insurance"]

PLANS = [
    {"key": "self-study", "name": "Self-Study", "sort_order": 1, "contact_only": False},
    {"key": "coaching", "name": "Coaching", "sort_order": 2, "contact_only": True},
]


def seed(db: Session) -> None:
    s = get_settings()
    langs = {}
    for spec in LANGUAGES:
        lang = db.scalar(select(Language).where(Language.code == spec["code"]))
        if not lang:
            lang = Language(**spec)
            db.add(lang)
            db.flush()
            log.info("created language %s", spec["code"])
        langs[spec["code"]] = lang
    for code, lang in langs.items():
        if lang.language_type == LanguageType.LOTE:
            get_or_create_pair(db, langs["en"], lang)
            if code in SCORING and not db.scalar(select(LanguageScoringConfig).where(
                    LanguageScoringConfig.language_id == lang.id)):
                db.add(LanguageScoringConfig(language_id=lang.id, **SCORING[code]))

    for i, name in enumerate(TOPICS):
        if not db.scalar(select(Topic).where(Topic.name == name)):
            db.add(Topic(name=name, sort_order=i))

    prices = {"self-study": s.stripe_price_self_study, "coaching": s.stripe_price_coaching}
    for spec in PLANS:
        plan = db.scalar(select(Plan).where(Plan.key == spec["key"]))
        if not plan:
            plan = Plan(**spec)
            db.add(plan)
        if prices[spec["key"]]:
            plan.stripe_price_id = prices[spec["key"]]
            plan.contact_only = False

    if s.admin_email and s.admin_password:
        email = s.admin_email.strip().lower()
        admin = db.scalar(select(User).where(User.email == email))
        if not admin:
            db.add(User(email=email, first_name=s.admin_first_name, last_name=s.admin_last_name,
                        password_hash=hash_password(s.admin_password), role=UserRole.ADMIN))
            log.info("created admin %s", email)
        else:
            admin.role = UserRole.ADMIN
            if not verify_password(s.admin_password, admin.password_hash):
                admin.password_hash = hash_password(s.admin_password)
    db.commit()


# Development only (`python -m app.seed --dev`): clearly marked placeholder reviews so the layout can be checked.
DEV_REVIEWS = [
    {"name": "Sample reviewer", "text": "Sample review, replace before launch.", "rating": 5, "placeholder": True},
    {"name": "Sample reviewer", "text": "Sample review, replace before launch.", "rating": 5, "placeholder": True},
]


def seed_dev(db: Session) -> None:
    if get_settings().is_production:
        raise RuntimeError("--dev seed data must not be loaded in production")
    if not db.scalar(select(SiteContent).where(SiteContent.key == "reviews")):
        db.add(SiteContent(key="reviews", value=DEV_REVIEWS))
    db.commit()


def main() -> None:
    import sys

    logging.basicConfig(level=logging.INFO)
    with SessionLocal() as db:
        seed(db)
        if "--dev" in sys.argv:
            seed_dev(db)
    log.info("seed complete")


if __name__ == "__main__":
    main()
