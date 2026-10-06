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
