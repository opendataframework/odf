import pytest

from odf.ui import media


@pytest.mark.parametrize(
    ("content", "default", "expected"),
    [
        (b"\x00\x00\x00\x18ftypisomrest", "video/mp4", "video/mp4"),
        (b"\x00\x00\x00\x18ftypisomrest", "audio/wav", "audio/mp4"),
        (b"\x00\x00\x00\x18ftypM4A rest", "video/mp4", "audio/mp4"),
        (b"\x00\x00\x00\x14ftypqt  rest", "video/mp4", "video/quicktime"),
        (b"\x1a\x45\xdf\xa3rest", "video/mp4", "video/webm"),
        (b"\x1a\x45\xdf\xa3rest", "audio/wav", "audio/webm"),
        (b"OggS\x00rest", "video/mp4", "video/ogg"),
        (b"OggS\x00rest", "audio/wav", "audio/ogg"),
        (b"RIFF\x00\x00\x00\x00WAVErest", "video/mp4", "audio/wav"),
        (b"RIFF\x00\x00\x00\x00AVI rest", "video/mp4", "video/x-msvideo"),
        (b"fLaC\x00rest", "audio/wav", "audio/flac"),
        (b"ID3\x04rest", "audio/wav", "audio/mpeg"),
        (b"\xff\xfb\x90\x00rest", "audio/wav", "audio/mpeg"),
        (b"\xff\xf1\x50\x80rest", "audio/wav", "audio/aac"),
        (b"unrecognised", "video/mp4", "video/mp4"),
        (b"unrecognised", "audio/wav", "audio/wav"),
        (b"", "audio/wav", "audio/wav"),
    ],
)
def test_sniff_media_type_detects_video_and_audio(content, default, expected):
    assert media.sniff_media_type(content, default) == expected


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (b"\xff\xd8\xff\xe0rest", "image/jpeg"),
        (b"\x89PNG\r\n\x1a\nrest", "image/png"),
        (b"\x00\x00\x00\x18ftypheicrest", "image/heic"),
        (b"\x00\x00\x00\x18ftypisomrest", "image/jpeg"),
        (b"unrecognised", "image/jpeg"),
    ],
)
def test_sniff_media_type_detects_images(content, expected):
    assert media.sniff_media_type(content, "image/jpeg") == expected


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n", "application/pdf"),
        (b"Receipt #102\nTotal: 54.00\n", "text/plain; charset=utf-8"),
        ("Total: 54,00 \u20ac".encode(), "text/plain; charset=utf-8"),
        ("Total: 54,00 \u20ac".encode()[:-1], "text/plain; charset=utf-8"),
        (b"PK\x03\x04\x14\x00\x06\x00", "application/octet-stream"),
        (b"caf\xe9 latin-1", "application/octet-stream"),
        (b"", "application/octet-stream"),
    ],
)
def test_sniff_media_type_detects_documents(content, expected):
    assert media.sniff_media_type(content, "application/octet-stream") == expected


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("bytes=2-5", (2, 5)),
        ("bytes=0-0", (0, 0)),
        ("bytes=4-", (4, 9)),
        ("bytes=-3", (7, 9)),
        ("bytes=-50", (0, 9)),
        ("bytes=8-50", (8, 9)),
        ("Bytes = 2-5", (2, 5)),
    ],
)
def test_parse_range_resolves_a_single_range(header, expected):
    assert media.parse_range(header, 10) == expected


@pytest.mark.parametrize(
    "header", [None, "", "items=0-1", "bytes=0-1,4-5", "bytes=abc", "bytes=-", "bytes=5-2"]
)
def test_parse_range_ignores_what_it_does_not_understand(header):
    assert media.parse_range(header, 10) is None


@pytest.mark.parametrize(("header", "size"), [("bytes=10-", 10), ("bytes=-0", 10), ("bytes=0-", 0)])
def test_parse_range_raises_for_a_range_outside_the_body(header, size):
    with pytest.raises(ValueError, match="unsatisfiable"):
        media.parse_range(header, size)


@pytest.mark.parametrize(
    ("content", "default", "declared", "expected"),
    [
        (b"unrecognised", "image/jpeg", "image/x-icon", "image/x-icon"),
        (b"\x89PNG\r\n\x1a\nrest", "image/jpeg", "Image/PNG; q=1", "image/png"),
        (b"\x89PNG\r\n\x1a\nrest", "image/jpeg", "image/svg+xml", "image/png"),
        (b"\x89PNG\r\n\x1a\nrest", "image/jpeg", "text/html", "image/png"),
        (b"unrecognised", "video/mp4", "audio/x-m4a", "audio/x-m4a"),
        (b"unrecognised", "audio/wav", "video/x-matroska", "video/x-matroska"),
        (b"ID3\x04rest", "audio/wav", "image/png", "audio/mpeg"),
        (b"ID3\x04rest", "audio/wav", None, "audio/mpeg"),
        (b"ID3\x04rest", "audio/wav", "", "audio/mpeg"),
    ],
)
def test_media_type_takes_a_declared_type_of_the_views_kind(content, default, declared, expected):
    assert media.media_type(content, default, declared) == expected


@pytest.mark.parametrize(
    ("content", "declared", "expected"),
    [
        (b"a,b\n1,2\n", "text/csv", "text/plain; charset=utf-8"),
        (b"<script>alert(1)</script>", "text/html", "text/plain; charset=utf-8"),
        (b"{}", "application/json", "text/plain; charset=utf-8"),
        (b"{}", "application/geo+json", "text/plain; charset=utf-8"),
        (b"<a/>", "application/xml", "text/plain; charset=utf-8"),
        (b"%PDF-1.7", "application/pdf", "application/pdf"),
        (b"Receipt", "application/pdf", "application/pdf"),
        (b"%PDF-1.7", "application/zip", "application/octet-stream"),
        (b"%PDF-1.7", None, "application/pdf"),
        (b"Receipt", None, "text/plain; charset=utf-8"),
    ],
)
def test_media_type_maps_a_declared_document_type_onto_the_document_rule(
    content, declared, expected
):
    assert media.media_type(content, "application/octet-stream", declared) == expected


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("report.pdf", "inline; filename=\"report.pdf\"; filename*=UTF-8''report.pdf"),
        ("../../etc/passwd", "inline; filename=\"passwd\"; filename*=UTF-8''passwd"),
        ("C:\\scans\\a.png", "inline; filename=\"a.png\"; filename*=UTF-8''a.png"),
        (
            'say "hi"\r\n.txt',
            "inline; filename=\"say _hi_.txt\"; filename*=UTF-8''say%20%22hi%22.txt",
        ),
        ("café.jpg", "inline; filename=\"cafe.jpg\"; filename*=UTF-8''caf%C3%A9.jpg"),
        (
            "отчёт.pdf",
            "inline; filename=\"_____.pdf\"; filename*=UTF-8''%D0%BE%D1%82%D1%87%D1%91%D1%82.pdf",
        ),
    ],
)
def test_content_disposition_names_the_content_safely(filename, expected):
    assert media.content_disposition(filename) == expected


@pytest.mark.parametrize("filename", [None, "", "  ", "dir/", "..", "\x00\x1f"])
def test_content_disposition_is_none_without_a_usable_name(filename):
    assert media.content_disposition(filename) is None
