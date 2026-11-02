"""Reading the text of a supplier's PDF, as rows of cells, with no PDF library.

Enough for invoices made of text in the standard fonts: it finds each page's
content streams (inflating compressed ones), follows the text operators to
place each string, and groups the strings into rows by height and into
cells by position. A scanned invoice, with no text in it, reads as nothing.
"""

import re
import zlib

_STREAM = re.compile(rb"stream\r?\n(.*?)endstream", re.DOTALL)
_TOKEN = re.compile(
    rb"\((?:\\.|[^\\()])*\)"  # a literal string
    rb"|<[0-9A-Fa-f\s]*>"  # a hex string
    rb"|/[^\s/\[\]()<>]+"  # a name
    rb"|[+-]?(?:\d+\.?\d*|\.\d+)"  # a number
    rb"|[\[\]]"  # an array's brackets
    rb"|[A-Za-z'\"*]+",  # an operator
    re.DOTALL,
)
_ESCAPES = {b"n": b"\n", b"r": b"\r", b"t": b"\t", b"b": b"\b", b"f": b"\f"}
# Points two strings' heights may differ by and still be on one row.
ROW_TOLERANCE = 2.0


def _string(token: bytes) -> str:
    """Decode a PDF string token, literal or hex, in WinAnsi."""
    if token.startswith(b"<"):
        digits = re.sub(rb"\s", b"", token[1:-1])
        return bytes.fromhex((digits + b"0" * (len(digits) % 2)).decode()).decode(
            "cp1252", "replace"
        )
    body, out, i = token[1:-1], bytearray(), 0
    while i < len(body):
        char = body[i : i + 1]
        if char != b"\\":
            out += char
            i += 1
            continue
        nxt = body[i + 1 : i + 2]
        if nxt.isdigit():
            octal = re.match(rb"[0-7]{1,3}", body[i + 1 : i + 4]).group()
            out.append(int(octal, 8) & 0xFF)
            i += 1 + len(octal)
        else:
            out += _ESCAPES.get(nxt, nxt)
            i += 2
    return out.decode("cp1252", "replace")


def _streams(data: bytes) -> list[bytes]:
    """Return every stream in ``data``, inflated where it's compressed."""
    found = []
    for raw in _STREAM.findall(data):
        try:
            # Lenient: the end-of-line before "endstream" is left on, and ignored.
            found.append(zlib.decompressobj().decompress(raw))
        except zlib.error:
            found.append(raw)
    return found


def _placed(content: bytes) -> list[tuple[float, float, str]]:
    """Return each string a content stream shows, as ``(x, y, text)``."""
    placed, operands = [], []
    x = y = line_x = line_y = 0.0
    leading = 12.0
    for token in _TOKEN.findall(content):
        if token[:1] in b"(<" or token[:1] == b"/" or re.fullmatch(rb"[+-]?[\d.]+", token):
            operands.append(token)
            continue
        if token in (b"[", b"]"):
            operands.append(token)
            continue
        numbers = [float(t) for t in operands if re.fullmatch(rb"[+-]?[\d.]+", t)]
        strings = [_string(t) for t in operands if t[:1] in b"(<"]
        if token == b"BT":
            x = y = line_x = line_y = 0.0
        elif token == b"Tm" and len(numbers) >= 6:
            x = line_x = numbers[-2]
            y = line_y = numbers[-1]
        elif token in (b"Td", b"TD") and len(numbers) >= 2:
            line_x += numbers[-2]
            line_y += numbers[-1]
            x, y = line_x, line_y
            if token == b"TD":
                leading = -numbers[-1]
        elif token == b"TL" and numbers:
            leading = numbers[-1]
        elif token in (b"T*", b"'", b'"'):
            line_y -= leading
            x, y = line_x, line_y
        if token in (b"Tj", b"TJ", b"'", b'"') and strings:
            placed.append((x, y, "".join(strings)))
        operands = []
    return placed


def pdf_rows(data: bytes) -> list[list[str]]:
    """Return the text of a PDF as rows of cells: top row first, each row's cells left to right."""
    placed = [p for stream in _streams(data) for p in _placed(stream) if p[2].strip()]
    rows: list[tuple[float, list[tuple[float, str]]]] = []
    for x, y, text in sorted(placed, key=lambda p: (-p[1], p[0])):
        if rows and abs(rows[-1][0] - y) <= ROW_TOLERANCE:
            rows[-1][1].append((x, text.strip()))
        else:
            rows.append((y, [(x, text.strip())]))
    return [[text for _, text in sorted(cells)] for _, cells in rows]


def pdf_text(data: bytes) -> str:
    """Return the text of a PDF, a line per row, its cells apart by two spaces."""
    return "\n".join("  ".join(row) for row in pdf_rows(data))
