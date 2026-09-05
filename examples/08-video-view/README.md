# 08 — Video View

A single `SecurityClips` repository implementing `data_view() -> VideoView`
instead of getting the default table. The topology UI renders it as a list
of seekable video clips, one per record, instead of a grid of columns.

This isolates the bounded, `ReadableProtocol` half of the concept covered in
[`opendataframework`'s view docs](https://opendataframework.github.io/opendataframework/view/):
`VideoView` needs `all()`, unlike
[`07-streaming-video-view`](../07-streaming-video-view)'s
`StreamingVideoView`, which needs `StreamableProtocol` instead — there is a
genuine "every record" here (a fixed list of stored clips), not a live feed.

`SecurityClips` comes pre-seeded in-memory with two synthesized clips (see
`app/repositories.py`'s `_SEED_CLIPS`) — there's no reason to reach for a
file when the data is this small, and a clip list is a lot more useful to
look at with something already in it.

## Structure

```
08-video-view/
├── config.toml          # no custom keys needed for this example
├── main.py              # entry point — reads back the pre-seeded clips, prints data_view()
└── app/
    ├── __init__.py      # imports both modules so decorators register at startup
    ├── entities.py       # SecurityClip(id, label, clip, recorded_at) — @Entity
    └── repositories.py   # SecurityClips — @Storage @Repository(SecurityClip), in-memory, pre-seeded
```

## Dependencies

Needs the `examples` extra (`pip install odf[examples]`), which pulls in
both `opencv-python` (`cv2`) and `numpy` to synthesize each clip as a short
mp4. Both are also in the repo's `dev` dependency group, so a plain
`poetry install` covers it too (see [`CLAUDE.md`](../../CLAUDE.md)). No
physical camera needed — every clip is generated in-process (a dot
sweeping across frames, color derived from a seed).

## Run it

```bash
cd examples/08-video-view
python main.py
```

Expected output (byte counts and the timestamp will vary):

```
All clips:
  SecurityClip(id=1, label='front-door', bytes=2874, recorded_at=1788040664.856506)
  SecurityClip(id=2, label='loading-dock', bytes=2958, recorded_at=1788040724.856506)

data_view() -> VideoView(field='clip')
```

Or start the dev UI and click **View Clips** on `SecurityClips`:

```bash
odf run
```

`GET /api/repositories` reports `SecurityClips`' view as
`{"kind": "video", "field": "clip"}` — that's what tells the UI to render a
list of seekable clips instead of a table.
