"""In-memory repository backing the image-view example."""

import time

import cv2
import numpy as np
from opendataframework import ImageView, Repository, Storage

from app.entities import DeliveryPhoto

_PHOTO_SIZE = (320, 240)  # (width, height)


def synth_photo_jpeg(order_id: int) -> bytes:
    """Generate a synthetic JPEG still — a solid color block (derived from
    ``order_id``, so each photo looks distinct) with the order id drawn on
    it via ``cv2.putText`` — no binary asset to commit.
    """
    width, height = _PHOTO_SIZE
    color = (int(order_id * 47) % 256, int(order_id * 91) % 256, int(order_id * 137) % 256)
    image = np.full((height, width, 3), color, dtype=np.uint8)
    cv2.putText(
        image,
        f"Order #{order_id}",
        (16, height // 2),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 255),
        2,
    )
    ok, buf = cv2.imencode(".jpg", image)
    return buf.tobytes() if ok else b""


# (order_id, captured_at offset in seconds from construction time) — so
# there are a couple of real photos to look at without hand-triggering a
# save() first.
_SEED_PHOTOS: tuple[tuple[int, float], ...] = (
    (101, -3600.0),
    (102, -1800.0),
)


@Storage
@Repository(DeliveryPhoto)
class DeliveryPhotos:
    """In-memory ``DeliveryPhotos`` repository, pre-seeded with ``_SEED_PHOTOS``.

    Kept in-memory on purpose — the concept here is ``data_view()``, not
    persistence (see ../02-data-analytics for a SQLite-backed repository).
    Pre-seeded, also on purpose — a photo grid is a lot more useful to look
    at with a couple of real photos already in it than an empty one.
    """

    def __init__(self) -> None:
        """Seed the in-memory photo list from ``_SEED_PHOTOS``."""
        now = time.time()
        self._photos: list[DeliveryPhoto] = [
            DeliveryPhoto(
                id=photo_id,
                order_id=order_id,
                image=synth_photo_jpeg(order_id),
                captured_at=now + offset,
            )
            for photo_id, (order_id, offset) in enumerate(_SEED_PHOTOS, start=1)
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
