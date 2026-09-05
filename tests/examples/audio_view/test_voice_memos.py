from app.entities import VoiceMemo
from app.repositories import VoiceMemos
from opendataframework import AudioView

# Deliberately builds VoiceMemos directly rather than going through
# Project/Context — same reason as the other examples' tests, see
# tests/examples/entity_repository/test_books.py.


def test_voice_memos_save_assigns_incrementing_ids():
    memos = VoiceMemos()
    seeded = len(memos.all())

    memos.save(VoiceMemo(id=None, clip=b"", recorded_at=1.0))
    memos.save(VoiceMemo(id=None, clip=b"", recorded_at=2.0))

    assert [m.id for m in memos.all()][seeded:] == [seeded + 1, seeded + 2]


def test_voice_memos_save_updates_existing_record():
    memos = VoiceMemos()
    before = len(memos.all())
    memos.save(VoiceMemo(id=None, clip=b"first", recorded_at=1.0))
    saved = memos.all()[-1]

    saved.clip = b"updated"
    memos.save(saved)

    assert len(memos.all()) == before + 1
    assert memos.all()[-1].clip == b"updated"


def test_voice_memos_delete_removes_record():
    memos = VoiceMemos()
    before = len(memos.all())
    memos.save(VoiceMemo(id=None, clip=b"", recorded_at=1.0))
    new_id = memos.all()[-1].id

    memos.delete(new_id)

    assert len(memos.all()) == before


def test_voice_memos_data_view_is_audio():
    memos = VoiceMemos()

    assert memos.data_view() == AudioView(field="clip")
