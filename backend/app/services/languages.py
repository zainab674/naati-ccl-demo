"""Language / LanguagePair rules from DATA_MODEL.md. Adding a LOTE = one Language row + one LanguagePair row."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Language, LanguagePair, LanguageType


class LanguageRuleError(ValueError):
    pass


def validate_pair(db: Session, english: Language, lote: Language, existing_id=None) -> None:
    if english.language_type != LanguageType.ENGLISH:
        raise LanguageRuleError("english_language_id must be the English language record")
    if lote.language_type != LanguageType.LOTE:
        raise LanguageRuleError("lote_language_id must be a LOTE language")
    if english.id == lote.id:
        raise LanguageRuleError("A language pair needs two different languages")
    dup = db.scalar(select(LanguagePair).where(LanguagePair.english_language_id == english.id,
                                               LanguagePair.lote_language_id == lote.id))
    if dup and dup.id != existing_id:
        raise LanguageRuleError("This language pair already exists")


def get_or_create_pair(db: Session, english: Language, lote: Language) -> LanguagePair:
    pair = db.scalar(select(LanguagePair).where(LanguagePair.english_language_id == english.id,
                                                LanguagePair.lote_language_id == lote.id))
    if pair:
        return pair
    validate_pair(db, english, lote)
    pair = LanguagePair(english_language_id=english.id, lote_language_id=lote.id,
                        display_name=f"{english.name} <-> {lote.name}")
    db.add(pair)
    db.flush()
    return pair


def english(db: Session) -> Language:
    lang = db.scalar(select(Language).where(Language.language_type == LanguageType.ENGLISH))
    if not lang:
        raise LanguageRuleError("English language record is missing (run `python -m app.seed`)")
    return lang


def lote_by_code(db: Session, code: str) -> Language | None:
    return db.scalar(select(Language).where(Language.code == code.strip().lower(),
                                            Language.language_type == LanguageType.LOTE))


def pair_for(db: Session, lote: Language) -> LanguagePair | None:
    return db.scalar(select(LanguagePair).where(LanguagePair.lote_language_id == lote.id))


def student_pair(db: Session, user, language: str = "") -> LanguagePair | None:
    """Which language pair a student's lists show. "" = the student's own language (all if not chosen),
    "all" = every language, otherwise a LOTE code. None means no filter."""
    if language == "all":
        return None
    lote = lote_by_code(db, language) if language else user.preferred_language
    if language and not lote:
        raise LanguageRuleError(f"Unknown language '{language}'")
    return pair_for(db, lote) if lote else None


def lotes_by_code(db: Session) -> dict[str, Language]:
    return {lang.code: lang for lang in db.scalars(select(Language).where(Language.language_type == LanguageType.LOTE))}
