from app.entities import DeliveryPhoto
from app.repositories import DeliveryPhotos
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


def test_delivery_photos_are_seeded_from_one_file_per_image_format():
    images = [p.image for p in DeliveryPhotos().all()]

    assert images[0].startswith(b"\xff\xd8\xff")  # JPEG
    assert images[1].startswith(b"\x89PNG")
    assert images[2][:4] == b"RIFF" and images[2][8:12] == b"WEBP"
