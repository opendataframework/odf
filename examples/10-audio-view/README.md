# 10 — Audio View

A single `VoiceMemos` repository implementing `data_view() -> AudioView`
instead of getting the default table. The topology UI renders it as a grid
of cards, one per record, each showing its clip's waveform and length.
Selecting a card opens the clip in a player and starts it.

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
grid of playable clips instead of a table.

Each clip is served from
`GET /api/repositories/voice-memos/records/{id}/media` with the media type
detected from its bytes (WAV, MP3, AAC, M4A, FLAC, Ogg, WebM), so `clip` isn't
limited to WAV, and with `Range` requests honored, which is what lets the
player seek. The waveform is drawn for clips up to 10 MB; a larger one shows
its length only.

## Annotating

Time ranges and points can be labelled on an open memo, for simple cases where
a one-off script over a player would be more than the job needs: marking
speech and silence, an event, an onset.

- Under the player is a timeline of the whole memo, with its waveform and a
  line where it is playing.
- The tools are in the rail at the top left. It opens on **Select** (`V`),
  which adds nothing; the tool picked is remembered in the browser.
- With **Label a range** (`R`), drag on the timeline, type the range's label
  and press `Enter`. Labels already used in the repository are listed under
  the input, and the last one is prefilled.
- With **Label a point** (`P`), click the timeline.
- `M` marks where the memo is playing instead, which is finer than the
  timeline on a long one: a point with **Label a point**, and with **Label a
  range** one end of the range, then the other. With the last label prefilled,
  `M` then `Enter` is enough.
- Select a range or a point and press `Delete` (or its `×`) to remove it, or
  select its label to change it. There is no move or resize. Ranges may
  overlap.
- A click on the timeline that makes or selects nothing seeks the memo there.
- `Esc` backs out of the label input, then a range started with `M`, then the
  selection, then the memo.

Every change is saved to `annotations.json` in the directory `odf run` was
started from (`[project] annotations-file` in `config.toml` names another
path). `annotations = false` under `[ui]` in `config.toml` turns annotating
off. The file looks like this:

```json
{
  "version": 1,
  "repositories": {
    "voice-memos": {
      "labels": ["speech", "cough"],
      "records": {
        "1": {
          "duration": 12.48,
          "annotations": [
            {"type": "range", "label": "speech", "start": 0.8, "end": 4.25},
            {"type": "point", "label": "cough", "at": 6.1}
          ]
        }
      }
    }
  }
}
```

- `records` is keyed by record key (as a string). A record with no marks has
  no entry.
- `start`, `end` and `at` are seconds from the start of the clip, to the
  millisecond, in time order. `duration` is the clip's length, so they can be
  normalised without opening it.
- `labels` lists the labels in use, in the order each was first used. A label
  nothing uses any more is dropped.

The file is plain JSON, so a pipeline reads it without importing `odf`, for
example to cut the labelled ranges out of a clip's samples:

```python
import json

block = json.load(open("annotations.json"))["repositories"]["voice-memos"]
for key, record in block["records"].items():
    samples, rate = load(key)  # the memo's samples and its sample rate
    for mark in record["annotations"]:
        if mark["type"] == "range":
            segment = samples[int(mark["start"] * rate) : int(mark["end"] * rate)]
```

A memo can also be given a class, from the row under the timeline (see
[`11-image-view`](../11-image-view#classifying)).
