# 07 — Streaming Video View

A single `Webcam` repository, stream-only (`StreamableProtocol`, no
`all()`/`save()`) with `data_view() -> StreamingVideoView`. The topology UI
renders it as a live video player with a Start/Stop toggle instead of a
table or a list of clips.

This isolates the "live feed" half of the concept covered in
[`opendataframework`'s view docs](https://opendataframework.github.io/opendataframework/view/):
`StreamingVideoView` needs
`StreamableProtocol`, not `ReadableProtocol` — there is no "every record" for
a webcam, only frames as they arrive. See
[`08-video-view`](../08-video-view) for the bounded, seekable counterpart
(`VideoView`, backed by `ReadableProtocol` instead).

## Structure

```
07-streaming-video-view/
├── config.toml          # webcam device index
├── main.py              # entry point — opens the stream and pulls a few frames
└── app/
    ├── __init__.py      # imports both modules so decorators register at startup
    ├── entities.py      # Frame(id, data, timestamp) — @Entity
    └── repositories.py  # Webcam — @Storage @Repository(Frame), stream-only
```

## Dependencies

Needs the `examples` extra (`pip install odf[examples]`) for `opencv-python`
(`cv2`) to grab and JPEG-encode frames — already in the repo's `dev`
dependency group, so a plain `poetry install` covers it (see
[`CLAUDE.md`](../../CLAUDE.md)). Also needs a physical webcam attached at the
configured `device` index (`0` by default).

## Run it

```bash
cd examples/07-streaming-video-view
python main.py
```

Expected output (frame byte counts will vary):

```
data_view() -> StreamingVideoView(field='data')
First 3 frames:
  Frame(id=1, bytes=25143, timestamp=1735603200.123)
  Frame(id=2, bytes=25098, timestamp=1735603200.156)
  Frame(id=3, bytes=25211, timestamp=1735603200.189)
```

Or start the dev UI and use `Webcam`'s **Start Streaming** then
**View Stream** actions:

```bash
odf run
```

`GET /api/repositories` reports `Webcam`'s view as
`{"kind": "streaming-video", "field": "data"}` — that's what tells the UI to
render a live player instead of a table.
