"""Object storage: S3-compatible (AWS S3 now, Hetzner Object Storage later; endpoint is configurable) or a local
directory for development and tests. Keys are relative paths like "media/<segment_id>/v1/index.m3u8".

Nothing in here hands out public links to protected audio: segment media is only ever streamed through the signed,
session-bound /api/media endpoints.
"""
import mimetypes
from functools import lru_cache
from pathlib import Path

from ..settings import get_settings


class Storage:
    def put(self, key: str, data: bytes, content_type: str | None = None) -> None:
        raise NotImplementedError

    def get(self, key: str) -> bytes | None:
        raise NotImplementedError

    def delete_prefix(self, prefix: str) -> None:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        """Delete one object; a missing key is not an error."""
        raise NotImplementedError

    def list(self, prefix: str) -> list[str]:
        raise NotImplementedError

    def exists(self, key: str) -> bool:
        return self.get(key) is not None


class LocalStorage(Storage):
    def __init__(self, root: Path):
        self.root = root.resolve()

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root not in p.parents:
            raise ValueError(f"Invalid storage key: {key}")
        return p

    def put(self, key, data, content_type=None):
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def get(self, key):
        p = self._path(key)
        return p.read_bytes() if p.is_file() else None

    def delete_prefix(self, prefix):
        base = self._path(prefix)
        if base.is_dir():
            for f in sorted(base.rglob("*"), reverse=True):
                f.unlink() if f.is_file() else f.rmdir()
            base.rmdir()
        elif base.is_file():
            base.unlink()

    def delete(self, key):
        p = self._path(key)
        if p.is_file():
            p.unlink()

    def list(self, prefix):
        base = self._path(prefix)
        if not base.is_dir():
            return []
        return sorted(str(f.relative_to(self.root).as_posix()) for f in base.rglob("*") if f.is_file())


class S3Storage(Storage):
    def __init__(self):
        import boto3
        from botocore.config import Config

        s = get_settings()
        self.bucket = s.s3_bucket
        self.client = boto3.client(
            "s3", endpoint_url=s.s3_endpoint_url or None, region_name=s.s3_region,
            aws_access_key_id=s.s3_access_key_id or None, aws_secret_access_key=s.s3_secret_access_key or None,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path" if s.s3_endpoint_url else "auto"},
                          retries={"max_attempts": 3}))

    def put(self, key, data, content_type=None):
        ctype = content_type or mimetypes.guess_type(key)[0] or "application/octet-stream"
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=ctype)

    def get(self, key):
        try:
            return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except self.client.exceptions.NoSuchKey:
            return None
        except Exception as e:  # botocore ClientError 404 on some S3-compatible providers
            if getattr(e, "response", {}).get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
                return None
            raise

    def list(self, prefix):
        keys, token = [], None
        while True:
            kw = {"Bucket": self.bucket, "Prefix": prefix.rstrip("/") + "/"}
            if token:
                kw["ContinuationToken"] = token
            r = self.client.list_objects_v2(**kw)
            keys += [o["Key"] for o in r.get("Contents", [])]
            if not r.get("IsTruncated"):
                return sorted(keys)
            token = r["NextContinuationToken"]

    def delete(self, key):
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def delete_prefix(self, prefix):
        keys = self.list(prefix)
        for i in range(0, len(keys), 1000):
            self.client.delete_objects(Bucket=self.bucket,
                                       Delete={"Objects": [{"Key": k} for k in keys[i:i + 1000]]})


class DbStorage(Storage):
    """Files in Postgres (stored_objects). For serverless hosts without a disk or object storage; fine for audio
    clips and recordings of a few MB. Use S3 for large volumes."""

    def put(self, key, data, content_type=None):
        from sqlalchemy.dialects.postgresql import insert

        from ..db import SessionLocal
        from ..models import StoredObject

        ctype = content_type or mimetypes.guess_type(key)[0] or "application/octet-stream"
        row = {"key": key, "data": data, "content_type": ctype, "size": len(data)}
        with SessionLocal() as db:
            db.execute(insert(StoredObject).values(**row).on_conflict_do_update(
                index_elements=[StoredObject.key], set_={"data": data, "content_type": ctype, "size": len(data)}))
            db.commit()

    def get(self, key):
        from sqlalchemy import select

        from ..db import SessionLocal
        from ..models import StoredObject

        with SessionLocal() as db:
            return db.scalar(select(StoredObject.data).where(StoredObject.key == key))

    def list(self, prefix):
        from sqlalchemy import select

        from ..db import SessionLocal
        from ..models import StoredObject

        # Keys under "<prefix>/": LIKE with "!" as the escape so "_" and "%" in keys match literally.
        like = prefix.rstrip("/").replace("!", "!!").replace("%", "!%").replace("_", "!_") + "/%"
        with SessionLocal() as db:
            return sorted(db.scalars(select(StoredObject.key).where(StoredObject.key.like(like, escape="!"))))

    def delete(self, key):
        from sqlalchemy import delete

        from ..db import SessionLocal
        from ..models import StoredObject

        with SessionLocal() as db:
            db.execute(delete(StoredObject).where(StoredObject.key == key))
            db.commit()

    def delete_prefix(self, prefix):
        from sqlalchemy import delete

        from ..db import SessionLocal
        from ..models import StoredObject

        keys = self.list(prefix)
        with SessionLocal() as db:
            db.execute(delete(StoredObject).where(StoredObject.key.in_(keys + [prefix])))
            db.commit()


@lru_cache
def get_storage() -> Storage:
    s = get_settings()
    if s.storage_backend == "local":
        return LocalStorage(s.local_storage_dir)
    if s.storage_backend == "db":
        return DbStorage()
    return S3Storage()
