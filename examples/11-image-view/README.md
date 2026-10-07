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

## Annotating

An open photo can be labelled with boxes, for simple cases where a separate
annotation tool or a one-off script would be more than the job needs:

- Drag on the photo to draw a box, type its label and press `Enter`. Labels
  already used in the repository are listed under the input, to click or to
  pick with `↓`/`↑` and `Enter`; typing narrows the list, and the last label
  is prefilled.
- Select a box and press `Delete` (or its `×`) to remove it. There is no move
  or resize: delete the box and draw it again. A label no box in the
  repository uses any more is dropped from the list.
- Select a box's label to change it.
- A box inside a larger one stays on top, so it can still be selected,
  whichever was drawn first.
- `Esc` backs out of the label input, then the selection, then the photo.

Every change is saved to `annotations.json` in the directory `odf run` was
started from (`[project] annotations-file` in `config.toml` names another
path). `annotations = false` under `[ui]` in `config.toml` turns annotating
off for a project that doesn't need it. The file looks like this:

```json
{
  "version": 1,
  "repositories": {
    "delivery-photos": {
      "labels": ["parcel", "door"],
      "records": {
        "1": {
          "width": 640,
          "height": 480,
          "annotations": [
            {"type": "box", "label": "parcel", "x": 212, "y": 230, "width": 150, "height": 98}
          ]
        }
      }
    }
  }
}
```

- `repositories` is keyed by repository id, and `records` by record key (as a
  string). A record with no boxes has no entry.
- `labels` lists the labels that repository's boxes use, in the order each was
  first used. A label no box uses any more is dropped, so a label's index is a
  stable class id only while every label before it stays in use.
- `x`, `y`, `width` and `height` are pixels in the image, with `x`/`y` the
  box's top-left corner. `width` and `height` on the record are the image's own
  size, so boxes can be normalised without opening the image.

The file is plain JSON, so a training pipeline reads it without importing
`odf`, and converts to whatever its model expects:

```python
import json

block = json.load(open("annotations.json"))["repositories"]["delivery-photos"]
for key, record in block["records"].items():
    W, H = record["width"], record["height"]
    for box in record["annotations"]:
        class_id = block["labels"].index(box["label"])
        x, y, w, h = box["x"], box["y"], box["width"], box["height"]
        coco = [x, y, w, h]
        voc = [x, y, x + w, y + h]  # xmin, ymin, xmax, ymax
        yolo = [class_id, (x + w / 2) / W, (y + h / 2) / H, w / W, h / H]
```

Coordinates follow the photo as the browser displays it, which applies any
EXIF rotation. A loader that ignores EXIF orientation by default (Pillow, for
one) needs it applied (`PIL.ImageOps.exif_transpose`) for the boxes to line up
on rotated phone photos.
