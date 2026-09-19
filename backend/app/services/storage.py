"""File storage that works on a read-only serverless filesystem.

Keys are relative paths like "media/<activity>/01/s000.ts" or "uploads/<attempt>/003.webm".
  read : bundled file under data/ (shipped with the deploy) if present, else the DB.
  write: always the DB (student recordings, content-studio audio). Small files only.
"""
from pathlib import Path

from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..models import StoredFile
from ..settings import BASE_DIR

BUNDLE = BASE_DIR / "data"


def _bundle_path(key: str) -> Path | None:
    p = (BUNDLE / key).resolve()
    if BUNDLE.resolve() in p.parents and p.is_file():
        return p
    return None


def read(key: str, db: Session | None = None) -> bytes | None:
    p = _bundle_path(key)
    if p:
        return p.read_bytes()
    own = db is None
    db = db or SessionLocal()
    try:
        row = db.get(StoredFile, key)
        return bytes(row.data) if row else None
    finally:
        if own:
            db.close()


def exists(key: str, db: Session | None = None) -> bool:
    return read(key, db) is not None


def write(key: str, data: bytes, content_type: str = "application/octet-stream", db: Session | None = None) -> str:
    own = db is None
    db = db or SessionLocal()
    try:
        row = db.get(StoredFile, key)
        if row:
            row.data, row.content_type = data, content_type
        else:
            db.add(StoredFile(key=key, data=data, content_type=content_type))
        db.commit()
    finally:
        if own:
            db.close()
    return key


def list_keys(prefix: str, db: Session) -> list[str]:
    """Files under a prefix, from the bundle and the DB."""
    names = set()
    d = BUNDLE / prefix
    if d.is_dir():
        names |= {f"{prefix}/{p.name}" for p in d.iterdir() if p.is_file()}
    names |= {k for (k,) in db.query(StoredFile.key).filter(StoredFile.key.like(f"{prefix}/%")).all()}
    return sorted(names)
