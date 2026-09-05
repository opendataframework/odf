"""Entities for the image-view example."""

from dataclasses import dataclass

from opendataframework import Entity


@Entity
@dataclass
class DeliveryPhoto:
    """A delivery proof-of-drop photo shown via ``DeliveryPhotos.data_view()``.

    Attributes:
        id: Primary key, ``None`` until ``DeliveryPhotos.save()`` assigns one.
        order_id: The order this photo is proof-of-delivery for.
        image: The photo, JPEG-encoded.
        captured_at: ``time.time()`` when the photo was captured.
    """

    id: int | None
    order_id: int
    image: bytes
    captured_at: float
