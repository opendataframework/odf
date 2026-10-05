"""In-memory repository backing the image-view example."""

import time
from pathlib import Path

from opendataframework import ImageView, Repository, Storage

from app.entities import DeliveryPhoto

_PHOTOS_DIR = Path(__file__).resolve().parent.parent / "data" / "photos"

# (file name under data/photos, order_id, captured_at offset in seconds from
# construction time) — one photo per image format, so there are a few real
# pictures to look at without hand-triggering a save() first.
_SEED_PHOTOS: tuple[tuple[str, int, float], ...] = (
    ("order-101.jpg", 101, -3600.0),
    ("order-102.png", 102, -1800.0),
    ("order-103.webp", 103, -600.0),
)


@Storage
@Repository(DeliveryPhoto)
class DeliveryPhotos:
    """In-memory ``DeliveryPhotos`` repository, pre-seeded with ``_SEED_PHOTOS``.

    Kept in-memory on purpose — the concept here is ``data_view()``, not
    persistence (see ../02-data-analytics for a SQLite-backed repository).
    Pre-seeded, also on purpose — a photo grid is a lot more useful to look
    at with a few real photos already in it than an empty one. The image
    files are only read once, here; ``image`` holds their encoded bytes.
    """

    def __init__(self) -> None:
        """Seed the in-memory photo list from ``_SEED_PHOTOS``."""
        now = time.time()
        self._photos: list[DeliveryPhoto] = [
            DeliveryPhoto(
                id=photo_id,
                order_id=order_id,
                image=(_PHOTOS_DIR / filename).read_bytes(),
                captured_at=now + offset,
            )
            for photo_id, (filename, order_id, offset) in enumerate(_SEED_PHOTOS, start=1)
        ]
        self._next_id = len(self._photos) + 1

    def all(self) -> list[DeliveryPhoto]:
        """Return every photo."""
        return list(self._photos)

    def save(self, photo: DeliveryPhoto) -> None:
        """Create or update a photo.

        Args:
            photo: The photo to persist. An unset ``id`` creates a new
                record and has one assigned; a set ``id`` updates the
                matching record in place.
        """
        if photo.id is None:
            photo.id = self._next_id
            self._next_id += 1
            self._photos.append(photo)
            return
        for i, existing in enumerate(self._photos):
            if existing.id == photo.id:
                self._photos[i] = photo
                return

    def delete(self, photo_id: int) -> None:
        """Delete the photo matching ``photo_id``, if one exists.

        Args:
            photo_id: The ``id`` of the photo to remove.
        """
        self._photos = [p for p in self._photos if p.id != photo_id]

    def data_view(self) -> ImageView:
        """Tell the UI to render these records as images, not a table.

        Returns:
            An ``ImageView`` keyed on the ``image`` field.
        """
        return ImageView(field="image")
