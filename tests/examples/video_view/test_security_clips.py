import pytest
from app import repositories
from app.entities import SecurityClip
from app.repositories import SecurityClips, synth_clip
from opendataframework import VideoView

# Deliberately builds SecurityClips directly rather than going through
# Project/Context — same reason as the other examples' tests, see
# tests/examples/entity_repository/test_books.py.


def test_security_clips_save_assigns_incrementing_ids():
    clips = SecurityClips()
    seeded = len(clips.all())

    clips.save(SecurityClip(id=None, label="front-door", clip=b"", recorded_at=1.0))
    clips.save(SecurityClip(id=None, label="loading-dock", clip=b"", recorded_at=2.0))

    assert [c.id for c in clips.all()][seeded:] == [seeded + 1, seeded + 2]


def test_security_clips_save_updates_existing_record():
    clips = SecurityClips()
    before = len(clips.all())
    clips.save(SecurityClip(id=None, label="front-door", clip=b"", recorded_at=1.0))
    saved = clips.all()[-1]

    saved.label = "front-door (renamed)"
    clips.save(saved)

    assert len(clips.all()) == before + 1
    assert clips.all()[-1].label == "front-door (renamed)"


def test_security_clips_delete_removes_record():
    clips = SecurityClips()
    before = len(clips.all())
    clips.save(SecurityClip(id=None, label="front-door", clip=b"", recorded_at=1.0))
    new_id = clips.all()[-1].id

    clips.delete(new_id)

    assert len(clips.all()) == before


def test_security_clips_data_view_is_video():
    clips = SecurityClips()

    assert clips.data_view() == VideoView(field="clip")


def test_synth_clip_returns_distinct_nonempty_bytes():
    first = synth_clip(1)
    second = synth_clip(2)

    assert isinstance(first, bytes) and len(first) > 0
    assert isinstance(second, bytes) and len(second) > 0
    assert first != second


def test_synth_clip_falls_back_to_a_codec_opencv_can_write(monkeypatch):
    monkeypatch.setattr(repositories, "_CLIP_CODECS", (("XXXX", ".mp4"), ("mp4v", ".mp4")))

    assert len(synth_clip(1)) > 0


def test_synth_clip_raises_when_opencv_can_write_no_codec(monkeypatch):
    monkeypatch.setattr(repositories, "_CLIP_CODECS", (("XXXX", ".mp4"),))

    with pytest.raises(RuntimeError, match="XXXX"):
        synth_clip(1)
