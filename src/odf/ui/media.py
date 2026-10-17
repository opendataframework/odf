"""Media type detection and byte-range parsing for record media.

Pure helpers behind ``UiServer.record_media``, mirroring ``ui/data.py``'s
shape: no HTTP concerns live here, only functions that ``ui/server.py``
wires to its route.
"""

import codecs
import unicodedata
from urllib.parse import quote

# ISO-BMFF major brands (bytes 8-12, after the ``ftyp`` box marker) of the
# still-image formats phones save by default.
_FTYP_IMAGE_TYPES: dict[bytes, str] = {
    b"avif": "image/avif",
    b"avis": "image/avif",
    b"heic": "image/heic",
    b"heix": "image/heic",
    b"hevc": "image/heic",
    b"hevx": "image/heic",
    b"mif1": "image/heif",
    b"msf1": "image/heif",
}

# How many leading bytes ``sniff_media_type`` looks at.
SNIFF_LENGTH = 12

# How many it looks at for a document, where telling text from binary takes
# more than a magic number.
DOCUMENT_SNIFF_LENGTH = 1024


# Declared document types served as plain text, besides any ``text/...``.
_TEXT_DOCUMENT_TYPES = frozenset({"application/json", "application/xml"})

_PLAIN_TEXT = "text/plain; charset=utf-8"


def media_type(content: bytes, default: str, declared: str | None) -> str:
    """Decide the type a record's media is served as.

    A repository's declared type (``ContentMetadata.content_type``) is taken
    over sniffing, which can't tell CSV from plain text or name a format it
    has no magic number for. It is only a hint, though, so it never widens
    what is served: a document is still a PDF, plain text or an opaque
    download, and a declared image, video or audio type is only taken when
    it is of the view's kind and can't run script.

    Args:
        content: The encoded media's leading bytes, as ``sniff_media_type``
            takes them.
        default: The view's default type, as ``sniff_media_type`` takes it.
        declared: The type the repository declared, or ``None``.

    Returns:
        The type to serve the media as.
    """
    declared = (declared or "").partition(";")[0].strip().lower()
    if not declared:
        return sniff_media_type(content, default)
    major = default.partition("/")[0]
    if major == "application":
        if declared == "application/pdf":
            return declared
        if (
            declared.startswith("text/")
            or declared in _TEXT_DOCUMENT_TYPES
            or declared.endswith(("+json", "+xml"))
        ):
            return _PLAIN_TEXT
        return default
    kinds = ("image",) if major == "image" else ("video", "audio")
    if declared.partition("/")[0] in kinds and declared != "image/svg+xml":
        return declared
    return sniff_media_type(content, default)


def content_disposition(filename: str | None) -> str | None:
    """Build an inline ``Content-Disposition`` naming a record's content.

    Args:
        filename: The declared file name (``ContentMetadata.filename``),
            which may come from anywhere, so any path is dropped and so are
            control characters.

    Returns:
        The header value, or ``None`` when no usable name is left.
    """
    name = (filename or "").replace("\\", "/").rpartition("/")[2]
    name = "".join(c for c in name if unicodedata.category(c)[0] != "C").strip()
    if name in ("", ".", ".."):
        return None
    fallback = "".join(
        c if c.isascii() and c not in '"\\' else "_"
        for c in unicodedata.normalize("NFKD", name)
        if not unicodedata.combining(c)
    )
    return f"inline; filename=\"{fallback}\"; filename*=UTF-8''{quote(name, safe='')}"


def sniff_media_type(content: bytes, default: str) -> str:
    """Detect encoded media's type from its leading magic bytes.

    A media view's field holds whatever the project stored, not necessarily
    the format the view is assumed to carry, and a browser only gets to play
    a clip (or explain one it can't decode, HEIC outside Safari, say) if it
    is told the real type.

    Args:
        content: The encoded media, or at least its first ``SNIFF_LENGTH``
            bytes.
        default: The media type to fall back on. Its major type also picks
            between the two readings of a container that holds either video
            or audio (MP4, WebM, Ogg): ``audio/...`` for an ``audio``
            default, ``video/...`` otherwise. An ``application/...`` default
            marks a document, detected as a PDF or as plain text.

    Returns:
        The detected media type, or ``default`` when nothing matches.
    """
    major = default.partition("/")[0]
    if major == "image":
        return _sniff_image_type(content, default)
    if major == "application":
        return _sniff_document_type(content, default)
    av = "audio" if major == "audio" else "video"
    if content[4:8] == b"ftyp":
        brand = content[8:12]
        if brand == b"qt  ":
            return "video/quicktime"
        if brand in (b"M4A ", b"M4B "):
            return "audio/mp4"
        return f"{av}/mp4"
    if content.startswith(b"\x1a\x45\xdf\xa3"):
        return f"{av}/webm"
    if content.startswith(b"OggS"):
        return f"{av}/ogg"
    if content[:4] == b"RIFF" and content[8:12] == b"WAVE":
        return "audio/wav"
    if content[:4] == b"RIFF" and content[8:12] == b"AVI ":
        return "video/x-msvideo"
    if content.startswith(b"fLaC"):
        return "audio/flac"
    if content.startswith(b"ID3"):
        return "audio/mpeg"
    if len(content) >= 2 and content[0] == 0xFF and content[1] & 0xE0 == 0xE0:
        # An MPEG audio frame sync. Layer bits of 00 mark ADTS (raw AAC),
        # anything else an MP3 (or MP1/MP2) frame.
        return "audio/aac" if content[1] & 0x06 == 0 else "audio/mpeg"
    return default


def _sniff_image_type(content: bytes, default: str) -> str:
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    if content.startswith(b"BM"):
        return "image/bmp"
    if content.startswith((b"II*\x00", b"MM\x00*")):
        return "image/tiff"
    if content[4:8] == b"ftyp":
        return _FTYP_IMAGE_TYPES.get(content[8:12], default)
    return default


def _sniff_document_type(content: bytes, default: str) -> str:
    if content.startswith(b"%PDF-"):
        return "application/pdf"
    if not content or b"\x00" in content:
        return default
    try:
        # Incremental, so a multi-byte character cut off by the sniff length
        # doesn't make text look binary.
        codecs.getincrementaldecoder("utf-8")().decode(content)
    except UnicodeDecodeError:
        return default
    return "text/plain; charset=utf-8"


def parse_range(header: str | None, size: int) -> tuple[int, int] | None:
    """Resolve a request's ``Range`` header against a body of ``size`` bytes.

    Browsers seek within a clip, and Safari plays one at all, only through
    single byte ranges, so that is all this understands.

    Args:
        header: The raw ``Range`` header value, or ``None`` if there was none.
        size: The full body's length in bytes.

    Returns:
        The inclusive ``(start, end)`` byte positions to serve, or ``None``
        to serve the whole body: no header, a unit other than ``bytes``, a
        multi-range, or a range that can't be parsed.

    Raises:
        ValueError: If the range is well-formed but lies outside the body.
    """
    if header is None:
        return None
    unit, _, spec = header.partition("=")
    if unit.strip().lower() != "bytes" or "," in spec:
        return None
    first, dash, last = spec.strip().partition("-")
    if not dash or not (first or last) or not (first + last).isdigit():
        return None
    if not first:
        # A suffix range: the final ``last`` bytes.
        length = int(last)
        if length == 0 or size == 0:
            raise ValueError("unsatisfiable range")
        return max(0, size - length), size - 1
    start = int(first)
    if start >= size:
        raise ValueError("unsatisfiable range")
    end = min(int(last), size - 1) if last else size - 1
    if end < start:
        return None
    return start, end
