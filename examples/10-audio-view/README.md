# 10 — Audio View

A single `VoiceMemos` repository implementing `data_view() -> AudioView`
instead of getting the default table. The topology UI renders it as a list
of seekable audio clips, one per record, instead of a grid of columns.

This is the bounded, `ReadableProtocol` counterpart to
[`09-streaming-audio-view`](../09-streaming-audio-view)'s
`StreamingAudioView`, and the audio counterpart to
[`08-video-view`](../08-video-view)'s `VideoView` — same "a fixed list of
stored clips, not a live feed" shape, different media.

`VoiceMemos` comes pre-seeded in-memory with two synthesized tones (see
`app/repositories.py`'s `_SEED_MEMOS`) — there's no reason to reach for a
file when the data is this small, and a memo list is a lot more useful to
look at with something already in it.

## Structure

```
10-audio-view/
├── config.toml          # no custom keys needed for this example
├── main.py              # entry point — reads back the pre-seeded memos, prints data_view()
└── app/
    ├── __init__.py      # imports all modules so decorators register at startup
    ├── audio.py           # synth_tone_wav() — stdlib wave/struct sine-tone synth
    ├── entities.py         # VoiceMemo(id, clip, recorded_at) — @Entity
    └── repositories.py     # VoiceMemos — @Storage @Repository(VoiceMemo), in-memory, pre-seeded
```

## Dependencies

None beyond `opendataframework` itself and the Python standard library — `synth_tone_wav()`
uses only `wave`/`struct`/`math`, no ffmpeg or audio library.

## Run it

```bash
cd examples/10-audio-view
python main.py
```

Expected output (byte counts and timestamps will vary):

```
All memos:
  VoiceMemo(id=1, bytes=16044, recorded_at=1788040849.246924)
  VoiceMemo(id=2, bytes=16044, recorded_at=1788040909.246924)

data_view() -> AudioView(field='clip')
```

Or start the dev UI and click **View Clips** on `VoiceMemos`:

```bash
odf run
```

`GET /api/repositories` reports `VoiceMemos`' view as
`{"kind": "audio", "field": "clip"}` — that's what tells the UI to render a
list of seekable clips instead of a table.
