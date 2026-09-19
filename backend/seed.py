"""Reset the database and seed the demo (local use).

    python seed.py            # reset DB; voice any changed segments (cached by text hash)
    python seed.py --fresh    # also regenerate all audio

Commit data/media and data/seed_audio afterwards: the deployed app seeds itself
from those bundled files and never runs TTS on boot.
"""
import sys

from app.db import Base, SessionLocal, engine
from app.models import Attempt
from app.seeding import USERS, PASSWORD, seed_database
from app.services.scoring import attempt_results
from app.settings import get_settings


def main():
    print("Resetting database...")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    seed_database(db, generate_media=True, fresh="--fresh" in sys.argv)
    print(f"Marker: {get_settings().resolved_marker}")
    for att in db.query(Attempt).order_by(Attempt.started_at).all():
        r = attempt_results(db, att)
        print(f"  {att.mode:8s} {r['total']}/{r['total_max']} "
              f"({', '.join(str(d['score']) for d in r['dialogues'])}) passed={r['passed']}")
    db.close()
    print(f"\nDone. Logins (password: {PASSWORD}):")
    for email, _, role, _, _ in USERS:
        print(f"  {role:9s} {email}")


if __name__ == "__main__":
    main()
