"""Learning hub files and rules: which file types may be uploaded, where they are stored, when a resource can be
published. Files live in private storage and reach students only through the authenticated /api/resources/{id}/file
endpoint."""
import re
import unicodedata
import uuid
from collections.abc import Callable
from pathlib import PurePath
from urllib.parse import quote

from ..models import Resource, ResourceType
from .imports.common import valid_url
from .storage import get_storage

# extension -> (content type, shown inline in the browser?, check of the first bytes)
FILE_TYPES: dict[str, tuple[str, bool, Callable[[bytes], bool]]] = {
    ".pdf": ("application/pdf", True, lambda b: b.startswith(b"%PDF")),
    ".epub": ("application/epub+zip", False, lambda b: b.startswith(b"PK\x03\x04")),
    ".docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", False,
              lambda b: b.startswith(b"PK\x03\x04")),
    ".xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", False,
              lambda b: b.startswith(b"PK\x03\x04")),
    ".pptx": ("application/vnd.openxmlformats-officedocument.presentationml.presentation", False,
              lambda b: b.startswith(b"PK\x03\x04")),
    ".mp3": ("audio/mpeg", True, lambda b: b.startswith(b"ID3") or (len(b) > 1 and b[0] == 0xFF and b[1] & 0xE0 == 0xE0)),
    ".m4a": ("audio/mp4", True, lambda b: b[4:8] == b"ftyp"),
    ".wav": ("audio/wav", True, lambda b: b.startswith(b"RIFF") and b[8:12] == b"WAVE"),
    ".mp4": ("video/mp4", True, lambda b: b[4:8] == b"ftyp"),
    ".png": ("image/png", True, lambda b: b.startswith(b"\x89PNG")),
    ".jpg": ("image/jpeg", True, lambda b: b.startswith(b"\xff\xd8")),
    ".jpeg": ("image/jpeg", True, lambda b: b.startswith(b"\xff\xd8")),
}
SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


class ResourceError(ValueError):
    pass


def check_file(name: str, data: bytes) -> tuple[str, str]:
    """Returns (clean file name, content type). The type comes from our allow-list, never from the browser."""
    ext = PurePath(name).suffix.lower()
    if ext not in FILE_TYPES:
        raise ResourceError(f"File type {ext or '(none)'} is not allowed. Use one of: {', '.join(sorted(FILE_TYPES))}")
    ctype, _, looks_right = FILE_TYPES[ext]
    if not data:
        raise ResourceError("The file is empty")
    if not looks_right(data[:16]):
        raise ResourceError(f"The file's content does not look like a {ext} file")
    base = unicodedata.normalize("NFKD", PurePath(name).stem).encode("ascii", "ignore").decode()
    clean = (SAFE_NAME.sub("-", base).strip("-.") or "file")[:100] + ext
    return clean, ctype


def store_file(r: Resource, name: str, data: bytes) -> None:
    clean, ctype = check_file(name, data)
    storage = get_storage()
    old = r.file_key
    # A new key per upload, so a student who opened the old version is not served a half-replaced file.
    r.file_key = f"resources/{r.id}/{uuid.uuid4().hex}/{clean}"
    storage.put(r.file_key, data, ctype)
    r.file_name, r.file_size, r.content_type = clean, len(data), ctype
    if old:
        storage.delete_prefix(old.rsplit("/", 1)[0])


def remove_file(r: Resource) -> None:
    if r.file_key:
        get_storage().delete_prefix(r.file_key.rsplit("/", 1)[0])
    r.file_key, r.file_name, r.file_size, r.content_type = "", "", 0, ""


def disposition(r: Resource) -> str:
    inline = FILE_TYPES.get(PurePath(r.file_name).suffix.lower(), ("", False, None))[1]
    return f"{'inline' if inline else 'attachment'}; filename=\"{r.file_name}\"; filename*=UTF-8''{quote(r.file_name)}"


def readiness_problems(r: Resource) -> list[str]:
    """What stops a resource from being published (its content must match its type)."""
    if r.external_url and not valid_url(r.external_url):
        return ["The external link must start with https://"]
    if r.resource_type == ResourceType.LINK:
        return [] if r.external_url else ["A link needs an external URL"]
    if r.resource_type == ResourceType.ARTICLE:
        return [] if r.html_content.strip() else ["An article needs text"]
    if not (r.file_key or r.external_url):
        return [f"A {r.resource_type.value.lower()} needs an uploaded file or an external URL"]
    return []
