"""Cover images for courses and resources (Round 1 revision). Stored like the logo: PNG, JPEG or WebP only, a new key per
upload so a cached copy is never half-replaced. The image_url carries a version, so browsers can cache it."""
import uuid

from fastapi.responses import Response

from ..settings import get_settings
from .storage import get_storage

TYPES = {"image/png": ("png", b"\x89PNG"), "image/jpeg": ("jpg", b"\xff\xd8"), "image/webp": ("webp", b"RIFF")}


class ImageError(ValueError):
    pass


def store(obj, folder: str, data: bytes) -> None:
    """obj is a Course or Resource. The type comes from the file's first bytes, never from its name."""
    limit = get_settings().content_image_max_mb * 1024 * 1024
    if len(data) > limit:
        raise ImageError(f"The image is larger than {get_settings().content_image_max_mb} MB")
    match = next((t for t, (_, magic) in TYPES.items() if data.startswith(magic)), None)
    if not match:
        raise ImageError("The image must be a PNG, JPEG or WebP file")
    storage = get_storage()
    old = obj.image_key
    obj.image_key = f"{folder}/{obj.id}/{uuid.uuid4().hex}.{TYPES[match][0]}"
    storage.put(obj.image_key, data, match)
    if old:
        storage.delete(old)


def remove(obj) -> None:
    if obj.image_key:
        get_storage().delete(obj.image_key)
    obj.image_key = ""


def url(obj, path: str) -> str | None:
    if not obj.image_key:
        return None
    return f"{path}?v={obj.image_key.rsplit('/', 1)[-1].split('.')[0]}"


def response(obj) -> Response | None:
    data = get_storage().get(obj.image_key) if obj.image_key else None
    if data is None:
        return None
    ext = obj.image_key.rsplit(".", 1)[-1]
    ctype = next(t for t, (e, _) in TYPES.items() if e == ext)
    return Response(data, media_type=ctype, headers={"Cache-Control": "private, max-age=31536000, immutable",
                                                     "X-Content-Type-Options": "nosniff"})
