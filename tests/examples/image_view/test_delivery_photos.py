from app.entities import DeliveryPhoto
from app.repositories import DeliveryPhotos, synth_photo_jpeg
from opendataframework import ImageView

# Deliberately builds DeliveryPhotos directly rather than going through
# Project/Context — same reason as the other examples' tests, see
# tests/examples/entity_repository/test_books.py.


def test_delivery_photos_save_assigns_incrementing_ids():
    photos = DeliveryPhotos()
    seeded = len(photos.all())

    photos.save(DeliveryPhoto(id=None, order_id=101, image=b"", captured_at=1.0))
    photos.save(DeliveryPhoto(id=None, order_id=102, image=b"", captured_at=2.0))

    assert [p.id for p in photos.all()][seeded:] == [seeded + 1, seeded + 2]


def test_delivery_photos_save_updates_existing_record():
    photos = DeliveryPhotos()
    before = len(photos.all())
    photos.save(DeliveryPhoto(id=None, order_id=101, image=b"", captured_at=1.0))
    saved = photos.all()[-1]

    saved.order_id = 999
    photos.save(saved)

    assert len(photos.all()) == before + 1
    assert photos.all()[-1].order_id == 999


def test_delivery_photos_delete_removes_record():
    photos = DeliveryPhotos()
    before = len(photos.all())
    photos.save(DeliveryPhoto(id=None, order_id=101, image=b"", captured_at=1.0))
    new_id = photos.all()[-1].id

    photos.delete(new_id)

    assert len(photos.all()) == before


def test_delivery_photos_data_view_is_image():
    photos = DeliveryPhotos()

    assert photos.data_view() == ImageView(field="image")


def test_synth_photo_jpeg_returns_distinct_nonempty_bytes():
    first = synth_photo_jpeg(101)
    second = synth_photo_jpeg(102)

    assert isinstance(first, bytes) and len(first) > 0
    assert isinstance(second, bytes) and len(second) > 0
    assert first != second
