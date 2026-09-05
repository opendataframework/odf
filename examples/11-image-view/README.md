# 11 — Image View

A single `DeliveryPhotos` repository implementing `data_view() -> ImageView`
instead of getting the default table. The topology UI renders it as a grid
of thumbnails, one per record, instead of a grid of columns.

This isolates the `ImageView` variant covered in
[`opendataframework`'s view docs](https://opendataframework.github.io/opendataframework/view/) —
a single still image per record,
`ReadableProtocol`-backed like [`08-video-view`](../08-video-view)'s
`VideoView` and [`10-audio-view`](../10-audio-view)'s `AudioView`, but one
image instead of a clip.

`DeliveryPhotos` comes pre-seeded in-memory with two synthesized photos (see
`app/repositories.py`'s `_SEED_PHOTOS`) — there's no reason to reach for a
file when the data is this small, and a photo grid is a lot more useful to
look at with something already in it.

## Structure

```
11-image-view/
├── config.toml          # no custom keys needed for this example
├── main.py              # entry point — reads back the pre-seeded photos, prints data_view()
└── app/
    ├── __init__.py      # imports both modules so decorators register at startup
    ├── entities.py       # DeliveryPhoto(id, order_id, image, captured_at) — @Entity
    └── repositories.py   # DeliveryPhotos — @Storage @Repository(DeliveryPhoto), in-memory, pre-seeded
```

## Dependencies

Needs the `examples` extra (`pip install odf[examples]`), which pulls in
both `opencv-python` (`cv2`) and `numpy` to synthesize each photo. Both are
also in the repo's `dev` dependency group, so a plain `poetry install`
covers it too (see [`CLAUDE.md`](../../CLAUDE.md)). No binary asset is
committed — each photo is a solid color block (derived from the order id)
with the order id drawn on it via `cv2.putText`.

## Run it

```bash
cd examples/11-image-view
python main.py
```

Expected output (byte counts and timestamps will vary):

```
All photos:
  DeliveryPhoto(id=1, order_id=101, bytes=4247, captured_at=1788037458.134099)
  DeliveryPhoto(id=2, order_id=102, bytes=4620, captured_at=1788039258.134099)

data_view() -> ImageView(field='image')
```

Or start the dev UI and click **View Photos** on `DeliveryPhotos`:

```bash
odf run
```

`GET /api/repositories` reports `DeliveryPhotos`' view as
`{"kind": "image", "field": "image"}` — that's what tells the UI to render a
grid of thumbnails instead of a table.
