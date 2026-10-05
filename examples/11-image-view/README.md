# 11 — Image View

A single `DeliveryPhotos` repository implementing `data_view() -> ImageView`
instead of getting the default table. The topology UI renders it as a grid
of thumbnails, one per record, instead of a grid of columns. Selecting a
thumbnail opens that image full size, with the record's other fields as a
caption.

This isolates the `ImageView` variant covered in
[`opendataframework`'s view docs](https://opendataframework.github.io/opendataframework/view/) —
a single still image per record,
`ReadableProtocol`-backed like [`08-video-view`](../08-video-view)'s
`VideoView` and [`10-audio-view`](../10-audio-view)'s `AudioView`, but one
image instead of a clip.

`DeliveryPhotos` comes pre-seeded with the three pictures in `data/photos/`
(see `app/repositories.py`'s `_SEED_PHOTOS`), one each as JPEG, PNG and WebP
— a photo grid is a lot more useful to look at with something already in it.
The files are read once at startup; the repository itself stays in-memory,
with each record's `image` field holding the encoded bytes.

## Structure

```
11-image-view/
├── config.toml          # no custom keys needed for this example
├── main.py              # entry point — reads back the pre-seeded photos, prints data_view()
├── data/
│   └── photos/          # order-101.jpg, order-102.png, order-103.webp — the seed pictures
└── app/
    ├── __init__.py      # imports both modules so decorators register at startup
    ├── entities.py       # DeliveryPhoto(id, order_id, image, captured_at) — @Entity
    └── repositories.py   # DeliveryPhotos — @Storage @Repository(DeliveryPhoto), in-memory, pre-seeded
```

## Dependencies

None beyond `odf` itself — the photos are plain files, read as bytes.

## Run it

```bash
cd examples/11-image-view
python main.py
```

Expected output (timestamps will vary):

```
All photos:
  DeliveryPhoto(id=1, order_id=101, bytes=40500, captured_at=1791198425.9238558)
  DeliveryPhoto(id=2, order_id=102, bytes=2676, captured_at=1791200225.9238558)
  DeliveryPhoto(id=3, order_id=103, bytes=13078, captured_at=1791201425.9238558)

data_view() -> ImageView(field='image')
```

Or start the dev UI and click **View Photos** on `DeliveryPhotos`:

```bash
odf run
```

`GET /api/repositories` reports `DeliveryPhotos`' view as
`{"kind": "image", "field": "image"}` — that's what tells the UI to render a
grid of thumbnails instead of a table.
