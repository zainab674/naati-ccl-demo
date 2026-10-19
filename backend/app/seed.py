"""Idempotent base data: languages, the EN<->FIL pair, topics, Filipino scoring config, plans, first admin.

    python -m app.seed

Safe to run on every deploy: existing rows are kept; the admin account is kept in sync with ADMIN_EMAIL /
ADMIN_PASSWORD. No demo students, reviews or prices are created here.
"""
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import SessionLocal
from .models import Language, LanguageScoringConfig, LanguageType, Plan, Topic, User, UserRole
from .security import hash_password, verify_password
from .services.languages import get_or_create_pair
from .settings import get_settings

log = logging.getLogger("seed")

LANGUAGES = [
    {"code": "en", "name": "English", "native_name": "English", "language_type": LanguageType.ENGLISH,
     "stt_code": "en"},
    {"code": "fil", "name": "Filipino", "native_name": "Filipino (Tagalog)", "language_type": LanguageType.LOTE,
     "stt_code": "tl"},
]

# Common CCL dialogue domains.
TOPICS = ["Health", "Legal", "Financial", "Education", "Community", "Consumer Affairs", "Immigration",
          "Employment", "Housing", "Social Services", "Business", "Insurance"]

# Starting guidance for the evaluator. To be reviewed by Benchmark's Filipino teachers (see BUILD_PLAN open questions).
FILIPINO_SCORING = {
    "grammar_guidelines": (
        "Filipino (Tagalog) as spoken in community settings. Check verb aspect (perfective/imperfective/contemplative) "
        "matches the time reference, correct focus/affix use, correct markers (ang/ng/sa, si/ni/kay) and linkers "
        "(na/-ng). Do not penalise acceptable spoken variation or common contractions."),
    "register_guidelines": (
        "Use a neutral-professional register suitable for an interpreter. Respect markers (po/opo, kayo/ninyo as "
        "polite forms) are expected when addressing the professional or an older client; a significantly casual or "
        "disrespectful rendering is a register error. Common English loanwords used in everyday Filipino "
        "(appointment, form, bill, schedule) are acceptable and are not errors."),
    "hesitation_markers": ["ah", "eh", "ano", "ano ba", "kuwan", "kwan", "parang", "e", "um", "uh"],
    "pronunciation_config": {"auto_deduct": False, "review_only": True},
    "ai_prompt_addition": (
        "Code-switching with common English words (Taglish) is normal in Filipino and is not an error as long as the "
        "segment is interpreted into Filipino and the meaning is conveyed. A segment answered fully in English when "
        "Filipino was required is an accuracy problem (meaning not transferred into the target language)."),
}

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
    get_or_create_pair(db, langs["en"], langs["fil"])

    for i, name in enumerate(TOPICS):
        if not db.scalar(select(Topic).where(Topic.name == name)):
            db.add(Topic(name=name, sort_order=i))

    if not db.scalar(select(LanguageScoringConfig).where(LanguageScoringConfig.language_id == langs["fil"].id)):
        db.add(LanguageScoringConfig(language_id=langs["fil"].id, **FILIPINO_SCORING))

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


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    with SessionLocal() as db:
        seed(db)
    log.info("seed complete")


if __name__ == "__main__":
    main()
