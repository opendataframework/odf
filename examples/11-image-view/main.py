"""View: ImageView, a single still image per record.

DeliveryPhotos implements data_view() -> ImageView instead of the default
table. The topology UI renders a grid of thumbnails, one per record, instead
of a grid of columns.

DeliveryPhotos comes pre-seeded in-memory (see app/repositories.py's
_SEED_PHOTOS) rather than seeded here, so there's already something to
look at — main.py only reads the photos back. Run from this directory:
`python main.py`, or `odf run` and click "View Photos" on DeliveryPhotos
in the UI.
"""

from app.repositories import DeliveryPhotos

from odf.server import Server

server = Server.from_config("config.toml")
server.start()

photos = server.context.get(DeliveryPhotos)

print("All photos:")
for photo in photos.all():
    print(
        f"  DeliveryPhoto(id={photo.id}, order_id={photo.order_id}, bytes={len(photo.image)}, "
        f"captured_at={photo.captured_at})"
    )

print(f"\ndata_view() -> {photos.data_view()}")

server.stop()
