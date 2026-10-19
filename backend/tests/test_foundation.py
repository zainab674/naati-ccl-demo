import pytest
from sqlalchemy import select

from app.models import Language, LanguagePair, LanguageScoringConfig, LanguageType, Plan, Topic, User, UserRole
from app.seed import seed
from app.services.languages import LanguageRuleError, validate_pair
from app.settings import ccl_config, scoring_config


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_seed_is_idempotent(db):
    seed(db)
    seed(db)
    assert db.query(Language).count() == 2
    assert db.query(LanguagePair).count() == 1
    assert db.query(Topic).count() >= 5
    assert db.query(Plan).count() == 2
    admin = db.scalar(select(User).where(User.email == "admin@test.local"))
    assert admin.role == UserRole.ADMIN
    fil = db.scalar(select(Language).where(Language.code == "fil"))
    assert fil.stt_code == "tl"
    cfg = db.scalar(select(LanguageScoringConfig).where(LanguageScoringConfig.language_id == fil.id))
    assert "ano" in cfg.hesitation_markers


def test_language_pair_rules(db):
    en = db.scalar(select(Language).where(Language.language_type == LanguageType.ENGLISH))
    fil = db.scalar(select(Language).where(Language.code == "fil"))
    with pytest.raises(LanguageRuleError):
        validate_pair(db, en, en)
    with pytest.raises(LanguageRuleError):
        validate_pair(db, fil, en)
    with pytest.raises(LanguageRuleError, match="already exists"):
        validate_pair(db, en, fil)
    # A new LOTE needs no schema change: just rows.
    hi = Language(code="hi", name="Hindi", language_type=LanguageType.LOTE)
    db.add(hi)
    db.flush()
    validate_pair(db, en, hi)


def test_scoring_config_matches_brief():
    s = scoring_config()
    p = s["penalties"]
    assert p["accuracy_completeness"]["omission"] == 1
    assert p["accuracy_completeness"]["distortion"] == 1
    assert p["accuracy_completeness"]["insertion"] == 1
    assert all(v == 0.5 for v in p["language_quality"].values())
    assert all(v == 0.5 for v in p["fluency"].values())
    assert s["timing"]["long_pause_seconds"] == 3
    assert s["timing"]["start_delay_seconds"] == 5
    assert (s["pass_total"], s["pass_min_per_dialogue"], s["dialogue_max"], s["total_max"]) == (63, 29, 45, 90)
    assert s["pronunciation_auto_deduct"] is False
    assert ccl_config()["mock_test"]["dialogues_per_test"] == 2
